//+------------------------------------------------------------------+
//|                                            Maybe HFT no LOCK.mq5 |
//|                                                         Mas Imam |
//|                                              wa.me/6289679369219 |
//+------------------------------------------------------------------+
#property copyright "Mas Imam"
#property link      "wa.me/6289679369219"
#property version   "3.00"
//+------------------------------------------------------------------+
//| Hedging EA - Main + Hedge (Max 2 positions, Pending follow SL)   |
//| MT5 Version - UNIVERSAL: Auto-adapt to ANY pair, ANY account     |
//| v3.00: AutoDetectDigit, Equity-based AutoLot, Cent Account       |
//+------------------------------------------------------------------+
#property strict

//--- Trading Parameters
input double   Lots        = 0.10;   // Manual Lot (if UseAutoLot = false)
input bool     UseAutoLot  = true;   // Enable Auto Lot based on Risk %
input double   RiskPercent = 1.0;    // Risk % dari Equity per trade
input int      StopLoss    = 1500;   // SL dalam point (otomatis sesuai digit pair)
input int      TakeProfit  = 0;      // TP dalam point (0 = tidak pakai TP, hanya trailing)
input int      Trailing    = 500;    // jarak trailing dalam point
input int      TrailStart  = 1000;   // minimal profit (point) sebelum trailing aktif
input int      XDistance   = 300;    // jarak pending dari SL
input int      Slippage    = 30;
input int      Magic       = 12345;
input int      StartDirection = 0;   // 0=BUY pertama, 1=SELL pertama

//--- Session Time Filter (GMT+0)
input bool     UseAsiaSession = true;       // SESI ASIA (00:00–07:00 GMT)
input bool     UseLondonOpen  = true;       // SESI LONDON OPEN (07:00–12:00 GMT)
input bool     UseLondonPeak  = true;       // SESI LONDON PEAK (12:00–17:00 GMT)
input bool     UseNYSession   = true;       // SESI NEW YORK (17:00–22:00 GMT)

//--- Risk Management Parameters
input int      MaxSpread   = 50;     // maksimal spread dalam point (0 = tidak check)
input double   MinMarginLevel = 200.0; // minimal margin level dalam % (0 = tidak check)
input int      ModifyThreshold = 2;   // threshold untuk modify pending (dalam point)

//--- Daily Loss Limit & Drawdown Protection
input bool     UseDailyLossLimit = true;  // Enable daily loss limit
input double   MaxDailyLoss = 100.0;     // Maksimal loss harian dalam currency (0 = tidak check)
input bool     StopTradingOnLossLimit = true; // Stop trading jika mencapai loss limit
input bool     CloseAllOnLossLimit = true;    // Tutup SEMUA order jika mencapai drawdown/loss limit
input bool     UseMaxDrawdown = true;    // Enable maximum drawdown protection
input double   MaxDrawdownPercent = 20.0; // Maksimal drawdown dalam % (0 = tidak check)
input double   InitialBalance = 0;        // Balance awal (0 = auto detect saat EA start)

//--- Break Even Function
input bool     UseBreakEven = true;      // Enable break even
input int      BreakEvenProfit = 500;    // Profit (point) untuk move SL ke break even
input int      BreakEvenOffset = 10;      // Offset dari break even (point, positif = lock profit kecil)

//--- Display & Logging
input bool     ShowInfo    = true;   // tampilkan info di chart
input bool     EnableLogging = true; // enable logging ke file

// Include library untuk trading
#include <Trade\Trade.mqh>
CTrade trade;

//--- Global Variables
double g_InitialBalance = 0;
datetime g_LastDayCheck = 0;
bool g_TradingStopped = false;
bool g_IsCentAccount = false;
double g_AdjustedDailyLoss = 0; // MaxDailyLoss adjusted for Cent

//--- Adaptive Symbol Properties (refreshed per tick where needed)
double g_TickValue = 0;
double g_TickSize = 0;
double g_ContractSize = 0;
double g_LotStep = 0.01;
double g_MinLot = 0.01;
double g_MaxLot = 100.0;
int    g_StopLevel = 0;

//+------------------------------------------------------------------+
//| Normalize Price to tick size                                      |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize > 0)
      return NormalizeDouble(MathRound(price / tickSize) * tickSize, _Digits);
   return NormalizeDouble(price, _Digits);
}

//+------------------------------------------------------------------+
//| Normalize Lot to lot step                                        |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   // Floor to nearest lot step
   lot = MathFloor(lot / g_LotStep) * g_LotStep;
   
   // Clamp to min/max
   if(lot < g_MinLot) lot = g_MinLot;
   if(lot > g_MaxLot) lot = g_MaxLot;
   
   // Determine decimal places from lot step
   int lotDigits = 0;
   double step = g_LotStep;
   while(MathFloor(step) != step && lotDigits < 8)
   {
      step *= 10;
      lotDigits++;
   }
   
   return NormalizeDouble(lot, lotDigits);
}

//+------------------------------------------------------------------+
//| Detect Filling Mode supported by broker/symbol                   |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING DetectFillingMode()
{
   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   
   if((filling & SYMBOL_FILLING_FOK) != 0)
      return ORDER_FILLING_FOK;
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      return ORDER_FILLING_IOC;
   else
      return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validasi Parameter
   if(Lots <= 0 || Lots > 100)
   {
      Print("ERROR: Lots must be between 0.01 and 100. Current value: ", Lots);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(StopLoss <= 0)
   {
      Print("ERROR: StopLoss must be > 0. Current value: ", StopLoss);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(Trailing <= 0)
   {
      Print("ERROR: Trailing must be > 0. Current value: ", Trailing);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(TrailStart < 0)
   {
      Print("ERROR: TrailStart must be >= 0. Current value: ", TrailStart);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(XDistance <= 0)
   {
      Print("ERROR: XDistance must be > 0. Current value: ", XDistance);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(StartDirection < 0 || StartDirection > 1)
   {
      Print("ERROR: StartDirection must be 0 (BUY) or 1 (SELL). Current value: ", StartDirection);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   if(Magic <= 0)
   {
      Print("ERROR: Magic must be > 0. Current value: ", Magic);
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   //--- Check Symbol
   if(!SymbolInfoInteger(Symbol(), SYMBOL_SELECT))
   {
      Print("ERROR: Symbol ", Symbol(), " is not available");
      return(INIT_FAILED);
   }
   
   //--- Check Trading Allowed
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      Print("ERROR: Trading is not allowed in terminal");
      return(INIT_FAILED);
   }
   
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      Print("ERROR: Trading is not allowed for EA");
      return(INIT_FAILED);
   }
   
   //--- Setup Trade
   trade.SetExpertMagicNumber(Magic);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFilling(DetectFillingMode());
   trade.SetAsyncMode(false);
   
   //--- Initialize Global Variables
   if(InitialBalance > 0)
      g_InitialBalance = InitialBalance;
   else
      g_InitialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   g_LastDayCheck = 0;
   g_TradingStopped = false;
   
   //--- Detect Symbol Properties
   g_TickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   g_TickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_ContractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   g_LotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   g_MinLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   g_MaxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   g_StopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   
   //--- Auto Detect Cent Account
   string accCurrency = AccountInfoString(ACCOUNT_CURRENCY);
   string currLower = accCurrency;
   StringToLower(currLower);
   if(StringFind(currLower, "cent") >= 0 || StringFind(accCurrency, "USC") >= 0)
   {
      g_IsCentAccount = true;
   }
   
   // MaxDailyLoss works in account currency units directly
   // On Cent: profits are in cents, so MaxDailyLoss should be in cents too
   g_AdjustedDailyLoss = MaxDailyLoss;
   
   //--- Robust Validation for SL/TP based on StopLevel
   if(StopLoss < g_StopLevel && g_StopLevel > 0)
   {
      Print("WARNING: StopLoss (", StopLoss, ") < Broker StopLevel (", g_StopLevel, "). May be adjusted at runtime.");
   }
   
   //--- Validate Risk Management Parameters
   if(UseDailyLossLimit && MaxDailyLoss <= 0)
      Print("WARNING: UseDailyLossLimit=true but MaxDailyLoss<=0. Daily loss limit disabled.");
   
   if(UseMaxDrawdown && MaxDrawdownPercent <= 0)
      Print("WARNING: UseMaxDrawdown=true but MaxDrawdownPercent<=0. Drawdown protection disabled.");
   
   if(UseBreakEven && BreakEvenProfit <= 0)
      Print("WARNING: UseBreakEven=true but BreakEvenProfit<=0. Break even disabled.");
   
   //--- Display Info
   if(ShowInfo)
   {
      Comment("EA HFT v3.00 Initialized\n",
              "Symbol: ", Symbol(), "\n",
              "Digits: ", _Digits, " | Point: ", DoubleToString(_Point, _Digits), "\n",
              "Tick Value: ", DoubleToString(g_TickValue, 6), " | Tick Size: ", DoubleToString(g_TickSize, _Digits), "\n",
              "Contract Size: ", g_ContractSize, "\n",
              "Lot Step: ", g_LotStep, " | Min Lot: ", g_MinLot, " | Max Lot: ", g_MaxLot, "\n",
              "StopLevel: ", g_StopLevel, " points\n",
              "Filling Mode: ", EnumToString(DetectFillingMode()), "\n",
              "Auto Lot: ", (UseAutoLot ? "ON (" + DoubleToString(RiskPercent, 1) + "% Equity)" : "OFF"), "\n",
              "Cent Account: ", (g_IsCentAccount ? "YES" : "NO"), "\n",
              "Magic: ", Magic, "\n",
              "Initial Balance: ", DoubleToString(g_InitialBalance, 2), " ", accCurrency);
   }
   
   Print("=== EA HFT v3.00 UNIVERSAL Initialized on ", Symbol(), " ===");
   Print("Symbol: ", Symbol(), " | Digits: ", _Digits, " | Point: ", DoubleToString(_Point, _Digits));
   Print("TickValue: ", DoubleToString(g_TickValue, 6), " | TickSize: ", DoubleToString(g_TickSize, _Digits));
   Print("LotStep: ", g_LotStep, " | MinLot: ", g_MinLot, " | MaxLot: ", g_MaxLot);
   Print("StopLevel: ", g_StopLevel, " | Filling: ", EnumToString(DetectFillingMode()));
   Print("Account: ", accCurrency, " | Cent: ", (g_IsCentAccount ? "YES" : "NO"));
   Print("Parameters: SL=", StopLoss, " pts, Trail=", Trailing, " pts, TrailStart=", TrailStart, " pts");
   Print("SL Distance: ", DoubleToString(StopLoss * _Point, _Digits), " price units");
   Print("Risk: ", (UseDailyLossLimit ? "DailyLoss=" + DoubleToString(g_AdjustedDailyLoss, 2) : "DailyLoss=OFF"),
         ", DD=", (UseMaxDrawdown ? DoubleToString(MaxDrawdownPercent, 2) + "%" : "OFF"),
         ", BE=", (UseBreakEven ? "ON" : "OFF"));

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Check Spread                                                      |
//+------------------------------------------------------------------+
bool CheckSpread()
{
   if(MaxSpread <= 0) return true;
   
   long spread = SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
   if(spread > MaxSpread)
   {
      if(EnableLogging)
         Print("Spread too wide: ", spread, " pts (Max: ", MaxSpread, ")");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Check Margin                                                      |
//+------------------------------------------------------------------+
bool CheckMargin(double requiredLots = 0)
{
   if(MinMarginLevel <= 0) return true;
   
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(marginLevel > 0 && marginLevel < MinMarginLevel)
   {
      if(EnableLogging)
         Print("Margin too low: ", DoubleToString(marginLevel, 2), "% (Min: ", DoubleToString(MinMarginLevel, 2), "%)");
      return false;
   }
   
   // Check free margin using OrderCalcMargin for accuracy
   if(requiredLots > 0)
   {
      double marginNeeded = 0;
      double price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      if(OrderCalcMargin(ORDER_TYPE_BUY, Symbol(), requiredLots, price, marginNeeded))
      {
         double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
         if(freeMargin < marginNeeded * 1.5)
         {
            if(EnableLogging)
               Print("Insufficient margin. Need: ", DoubleToString(marginNeeded * 1.5, 2), ", Free: ", DoubleToString(freeMargin, 2));
            return false;
         }
      }
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Log Trade                                                         |
//+------------------------------------------------------------------+
void LogTrade(string message)
{
   if(!EnableLogging) return;
   
   string filename = "EA_HFT_Log_" + TimeToString(TimeCurrent(), TIME_DATE) + ".txt";
   int file = FileOpen(filename, FILE_WRITE | FILE_READ | FILE_TXT);
   if(file != INVALID_HANDLE)
   {
      FileSeek(file, 0, SEEK_END);
      FileWrite(file, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), " - ", message);
      FileClose(file);
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Risk % from EQUITY                   |
//| Universal: works on any pair, any account type                   |
//+------------------------------------------------------------------+
double CalculateAutoLot()
{
   if(!UseAutoLot) return NormalizeLot(Lots);
   
   // Use EQUITY (not Balance) for risk calculation
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (RiskPercent / 100.0);
   
   // Refresh tick value every time (different per symbol!)
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = _Point;
   
   // Safety check
   if(tickValue <= 0 || tickSize <= 0 || point <= 0 || StopLoss <= 0)
   {
      Print("WARNING: Cannot calc lot. TickVal=", tickValue, " TickSize=", tickSize, " Point=", point);
      return NormalizeLot(g_MinLot);
   }
   
   // Value of 1 point move for 1.0 lot = (tickValue / tickSize) * point
   // This is universal for ANY pair:
   //   EURUSD 5d: tickVal~10, tickSize=0.00001, point=0.00001 → valPerPt = 10
   //   XAUUSD 2d: tickVal~1, tickSize=0.01, point=0.01 → valPerPt = 1
   //   USDJPY 3d: tickVal~6.7, tickSize=0.001, point=0.001 → valPerPt = 6.7
   double valuePerPoint = (tickValue / tickSize) * point;
   
   // Lot = RiskAmount / (StopLoss_in_points * valuePerPoint)
   double lot = riskAmount / ((double)StopLoss * valuePerPoint);
   
   return NormalizeLot(lot);
}

//+------------------------------------------------------------------+
//| Close all open positions and cancel pending orders               |
//+------------------------------------------------------------------+
void CloseAllOrders()
{
   Print("EMERGENCY: Closing all positions and cancelling pending orders...");
   LogTrade("EMERGENCY: Closing all orders and pending.");
   
   //--- Cancel Pending Orders
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetInteger(ORDER_MAGIC) == Magic && OrderGetString(ORDER_SYMBOL) == Symbol())
      {
         if(!trade.OrderDelete(ticket))
            Print("Failed delete pending: ", ticket, " Err: ", GetLastError());
      }
   }
   
   //--- Close Open Positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == Magic)
      {
         ulong ticket = PositionGetInteger(POSITION_TICKET);
         if(ticket > 0)
         {
            if(!trade.PositionClose(ticket))
               Print("Failed close position: ", ticket, " Err: ", GetLastError());
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if current GMT time is in an allowed session               |
//+------------------------------------------------------------------+
bool IsSessionAllowed()
{
   MqlDateTime dt;
   TimeGMT(dt);
   int hour = dt.hour;
   
   if(UseAsiaSession && hour >= 0 && hour < 7) return true;
   if(UseLondonOpen && hour >= 7 && hour < 12) return true;
   if(UseLondonPeak && hour >= 12 && hour < 17) return true;
   if(UseNYSession && hour >= 17 && hour < 22) return true;
   
   return false;
}

//+------------------------------------------------------------------+
//| Get Session Name                                                 |
//+------------------------------------------------------------------+
string GetCurrentSessionName()
{
   MqlDateTime dt;
   TimeGMT(dt);
   int hour = dt.hour;
   
   if(hour >= 0 && hour < 7) return "ASIA";
   if(hour >= 7 && hour < 12) return "LONDON OPEN";
   if(hour >= 12 && hour < 17) return "LONDON PEAK";
   if(hour >= 17 && hour < 22) return "NEW YORK";
   
   return "OFF-MARKET";
}

//+------------------------------------------------------------------+
//| Get Daily Profit (floating + closed)                             |
//+------------------------------------------------------------------+
double GetDailyProfit()
{
   double totalProfit = 0;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime todayStart = StructToTime(dt);
   
   //--- Floating profit from ALL open positions
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && 
         PositionGetInteger(POSITION_MAGIC) == Magic)
      {
         totalProfit += PositionGetDouble(POSITION_PROFIT)
                      + PositionGetDouble(POSITION_SWAP);
      }
   }
   
   //--- Closed deals today
   if(HistorySelect(todayStart, TimeCurrent()))
   {
      for(int i = 0; i < HistoryDealsTotal(); i++)
      {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket > 0)
         {
            if(HistoryDealGetString(ticket, DEAL_SYMBOL) == Symbol() &&
               HistoryDealGetInteger(ticket, DEAL_MAGIC) == Magic &&
               HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
            {
               totalProfit += HistoryDealGetDouble(ticket, DEAL_PROFIT);
               totalProfit += HistoryDealGetDouble(ticket, DEAL_SWAP);
               totalProfit += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            }
         }
      }
   }
   
   return totalProfit;
}

//+------------------------------------------------------------------+
//| Check Daily Loss Limit                                            |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit()
{
   if(!UseDailyLossLimit || g_AdjustedDailyLoss <= 0) return true;
   
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime currentDay = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   
   if(currentDay != g_LastDayCheck)
   {
      g_LastDayCheck = currentDay;
      g_TradingStopped = false;
   }
   
   if(g_TradingStopped) return false;
   
   double dailyProfit = GetDailyProfit();
   
   if(dailyProfit <= -g_AdjustedDailyLoss)
   {
      Print("WARNING: Daily loss limit! P/L=", DoubleToString(dailyProfit, 2), 
            " Limit=", DoubleToString(-g_AdjustedDailyLoss, 2));
      LogTrade("Daily loss limit reached: " + DoubleToString(dailyProfit, 2));
      
      if(StopTradingOnLossLimit)
      {
         if(CloseAllOnLossLimit) CloseAllOrders();
         g_TradingStopped = true;
         return false;
      }
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Check Maximum Drawdown (uses Equity)                             |
//+------------------------------------------------------------------+
bool CheckMaxDrawdown()
{
   if(!UseMaxDrawdown || MaxDrawdownPercent <= 0) return true;
   
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   if(g_InitialBalance <= 0)
   {
      g_InitialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      return true;
   }
   
   double drawdownPercent = ((g_InitialBalance - equity) / g_InitialBalance) * 100.0;
   
   if(drawdownPercent >= MaxDrawdownPercent)
   {
      Print("CRITICAL: DD=", DoubleToString(drawdownPercent, 2), "% >= Limit=", DoubleToString(MaxDrawdownPercent, 2), "%");
      LogTrade("Max DD reached: " + DoubleToString(drawdownPercent, 2) + "%");
      if(CloseAllOnLossLimit) CloseAllOrders();
      ExpertRemove();
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Count active positions                                           |
//+------------------------------------------------------------------+
int CountMainOrders()
{
   int count=0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == Magic)
         count++;
   }
   return(count);
}

//+------------------------------------------------------------------+
//| Count pending orders                                             |
//+------------------------------------------------------------------+
int CountPendingOrders()
{
   int count=0;
   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      if(OrderGetTicket(i))
      {
         if(OrderGetString(ORDER_SYMBOL) == Symbol() && 
            OrderGetInteger(ORDER_MAGIC) == Magic &&
            (OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP || 
             OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_SELL_STOP))
            count++;
      }
   }
   return(count);
}

//+------------------------------------------------------------------+
//| Open main order                                                  |
//+------------------------------------------------------------------+
void OpenMainOrder(int direction)
{
   if(!CheckSpread())
   {
      LogTrade("Skip open: Spread too wide");
      return;
   }
   
   double currentLots = CalculateAutoLot();
   
   if(!CheckMargin(currentLots))
   {
      LogTrade("Skip open: Insufficient margin");
      return;
   }
   
   double price, sl, tp = 0;
   double point = _Point;
   
   if(point <= 0)
   {
      Print("ERROR: Invalid point for ", Symbol());
      return;
   }
   
   // Respect broker StopLevel
   int effectiveSL = StopLoss;
   int stopLevel = (int)SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL);
   if(stopLevel > 0 && effectiveSL < stopLevel)
      effectiveSL = stopLevel;
   
   if(direction == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      if(price <= 0) { Print("ERROR: Invalid ASK"); return; }
      
      sl = NormalizePrice(price - effectiveSL * point);
      if(TakeProfit > 0)
         tp = NormalizePrice(price + TakeProfit * point);
      
      double minStopDist = stopLevel * point;
      if(minStopDist > 0 && (price - sl) < minStopDist)
      {
         Print("ERROR: SL too close. Min=", stopLevel, " pts");
         return;
      }
      
      if(!trade.Buy(currentLots, Symbol(), price, sl, tp, "Main BUY"))
      {
         Print("ERROR BUY: ", trade.ResultRetcodeDescription(),
               " P=", DoubleToString(price, _Digits), " SL=", DoubleToString(sl, _Digits));
         LogTrade("ERROR BUY: " + trade.ResultRetcodeDescription());
      }
      else
      {
         Print("BUY OK: ", DoubleToString(price, _Digits), " SL=", DoubleToString(sl, _Digits),
               (tp > 0 ? " TP=" + DoubleToString(tp, _Digits) : ""), " Lot=", DoubleToString(currentLots, 2));
         LogTrade("BUY: " + DoubleToString(price, _Digits) + " SL=" + DoubleToString(sl, _Digits));
      }
   }
   else if(direction == ORDER_TYPE_SELL)
   {
      price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      if(price <= 0) { Print("ERROR: Invalid BID"); return; }
      
      sl = NormalizePrice(price + effectiveSL * point);
      if(TakeProfit > 0)
         tp = NormalizePrice(price - TakeProfit * point);
      
      double minStopDist = stopLevel * point;
      if(minStopDist > 0 && (sl - price) < minStopDist)
      {
         Print("ERROR: SL too close. Min=", stopLevel, " pts");
         return;
      }
      
      if(!trade.Sell(currentLots, Symbol(), price, sl, tp, "Main SELL"))
      {
         Print("ERROR SELL: ", trade.ResultRetcodeDescription(),
               " P=", DoubleToString(price, _Digits), " SL=", DoubleToString(sl, _Digits));
         LogTrade("ERROR SELL: " + trade.ResultRetcodeDescription());
      }
      else
      {
         Print("SELL OK: ", DoubleToString(price, _Digits), " SL=", DoubleToString(sl, _Digits),
               (tp > 0 ? " TP=" + DoubleToString(tp, _Digits) : ""), " Lot=", DoubleToString(currentLots, 2));
         LogTrade("SELL: " + DoubleToString(price, _Digits) + " SL=" + DoubleToString(sl, _Digits));
      }
   }
}

//+------------------------------------------------------------------+
//| Trailing + Break Even (universal with _Point)                    |
//+------------------------------------------------------------------+
void TrailOrders()
{
   double point = _Point;
   if(point <= 0) return;
   
   double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return;
   
   double minStopLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL) * point;
   
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == Magic)
      {
         ulong ticket = PositionGetInteger(POSITION_TICKET);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double curSL = PositionGetDouble(POSITION_SL);
         double curTP = PositionGetDouble(POSITION_TP);
         ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         
         if(posType == POSITION_TYPE_BUY)
         {
            double profitPts = (bid - openPrice) / point;
            double newSL = curSL;
            bool doModify = false;
            
            // Break Even (before trailing)
            if(UseBreakEven && BreakEvenProfit > 0 && 
               profitPts >= BreakEvenProfit && profitPts < TrailStart)
            {
               newSL = openPrice + (BreakEvenOffset * point);
               if(minStopLevel > 0 && (bid - newSL) < minStopLevel)
                  newSL = bid - minStopLevel;
               newSL = NormalizePrice(newSL);
               if(newSL > curSL && newSL < bid - minStopLevel)
               {
                  doModify = true;
                  if(EnableLogging) LogTrade("BE BUY: SL→" + DoubleToString(newSL, _Digits));
               }
            }
            // Trailing (after TrailStart)
            else if(profitPts > TrailStart)
            {
               newSL = bid - Trailing * point;
               if(minStopLevel > 0 && (bid - newSL) < minStopLevel)
                  newSL = bid - minStopLevel;
               if(newSL > curSL && newSL < bid)
                  doModify = true;
            }
            
            if(doModify)
            {
               if(!trade.PositionModify(ticket, newSL, curTP))
               {
                  int err = GetLastError();
                  if(err != 10004)
                     Print("ERROR trail BUY: ", trade.ResultRetcodeDescription());
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double profitPts = (openPrice - ask) / point;
            double newSL = curSL;
            bool doModify = false;
            
            // Break Even (before trailing)
            if(UseBreakEven && BreakEvenProfit > 0 && 
               profitPts >= BreakEvenProfit && profitPts < TrailStart)
            {
               newSL = openPrice - (BreakEvenOffset * point);
               if(minStopLevel > 0 && (newSL - ask) < minStopLevel)
                  newSL = ask + minStopLevel;
               newSL = NormalizePrice(newSL);
               if((newSL < curSL || curSL == 0) && newSL > ask + minStopLevel)
               {
                  doModify = true;
                  if(EnableLogging) LogTrade("BE SELL: SL→" + DoubleToString(newSL, _Digits));
               }
            }
            // Trailing (after TrailStart)
            else if(profitPts > TrailStart)
            {
               newSL = ask + Trailing * point;
               if(minStopLevel > 0 && (newSL - ask) < minStopLevel)
                  newSL = ask + minStopLevel;
               if((newSL < curSL || curSL == 0) && newSL > ask)
                  doModify = true;
            }
            
            if(doModify)
            {
               if(!trade.PositionModify(ticket, newSL, curTP))
               {
                  int err = GetLastError();
                  if(err != 10004)
                     Print("ERROR trail SELL: ", trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Handle pending (create/modify hedge)                             |
//+------------------------------------------------------------------+
void HandlePending()
{
   if(!CheckSpread()) return;
   
   double currentLots = CalculateAutoLot();
   if(!CheckMargin(currentLots)) return;
   
   ENUM_POSITION_TYPE mainType = -1;
   double mainSL = 0;
   ulong hedgeTicket = 0;
   ENUM_ORDER_TYPE hedgeType = -1;
   double point = _Point;
   
   if(point <= 0) return;

   double newPrice = 0, newSL = 0;

   // Find main position
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == Magic)
      {
         mainType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         mainSL = PositionGetDouble(POSITION_SL);
         break;
      }
   }
   
   // Find pending order
   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0)
      {
         if(OrderGetString(ORDER_SYMBOL) == Symbol() && 
            OrderGetInteger(ORDER_MAGIC) == Magic &&
            (OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP || 
             OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_SELL_STOP))
         {
            hedgeTicket = ticket;
            hedgeType = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
            break;
         }
      }
   }

   if(mainType == -1) return;
   if(CountMainOrders() >= 2) return;

   double stopsLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL) * point;
   double minDistance = MathMax(stopsLevel, SymbolInfoInteger(Symbol(), SYMBOL_TRADE_FREEZE_LEVEL) * point);
   double currentPrice = SymbolInfoDouble(Symbol(), (mainType == POSITION_TYPE_BUY ? SYMBOL_BID : SYMBOL_ASK));
   
   if(mainType == POSITION_TYPE_BUY && mainSL > 0)
   {
      newPrice = mainSL + XDistance * point;
      if(newPrice > currentPrice - minDistance)
         newPrice = currentPrice - minDistance - point;
      newSL = newPrice + StopLoss * point;
      
      newPrice = NormalizePrice(newPrice);
      newSL = NormalizePrice(newSL);
      
      if(hedgeTicket == 0)
      {
         if(!trade.SellStop(currentLots, newPrice, Symbol(), newSL, 0, ORDER_TIME_GTC, 0, "Hedge SELL STOP"))
         {
            Print("ERROR SELL STOP: ", trade.ResultRetcodeDescription());
            LogTrade("ERROR SELL STOP: " + trade.ResultRetcodeDescription());
         }
         else
         {
            Print("SELL STOP: ", DoubleToString(newPrice, _Digits), " SL=", DoubleToString(newSL, _Digits));
            LogTrade("SELL STOP: " + DoubleToString(newPrice, _Digits));
         }
      }
      else if(hedgeType == ORDER_TYPE_SELL_STOP)
      {
         double curPP = OrderGetDouble(ORDER_PRICE_OPEN);
         double curPS = OrderGetDouble(ORDER_SL);
         
         double bidPrice = SymbolInfoDouble(Symbol(), SYMBOL_BID);
         double freezeLevel = MathMax(10, SymbolInfoInteger(Symbol(), SYMBOL_TRADE_FREEZE_LEVEL)) * point;
         if(MathAbs(bidPrice - curPP) <= freezeLevel) return;
         
         double threshold = ModifyThreshold * point;
         if(MathAbs(curPP - newPrice) > threshold || MathAbs(curPS - newSL) > threshold)
         {
            ResetLastError();
            if(!trade.OrderModify(hedgeTicket, newPrice, newSL, 0, ORDER_TIME_GTC, 0))
            {
               int err = GetLastError();
               if(err != 10004 && err != 4756)
                  Print("ERROR mod SELL STOP: ", trade.ResultRetcodeDescription());
            }
         }
      }
   }
   else if(mainType == POSITION_TYPE_SELL && mainSL > 0)
   {
      newPrice = mainSL - XDistance * point;
      if(newPrice < currentPrice + minDistance)
         newPrice = currentPrice + minDistance + point;
      newSL = newPrice - StopLoss * point;
      
      newPrice = NormalizePrice(newPrice);
      newSL = NormalizePrice(newSL);
      
      if(hedgeTicket == 0)
      {
         if(!trade.BuyStop(currentLots, newPrice, Symbol(), newSL, 0, ORDER_TIME_GTC, 0, "Hedge BUY STOP"))
         {
            Print("ERROR BUY STOP: ", trade.ResultRetcodeDescription());
            LogTrade("ERROR BUY STOP: " + trade.ResultRetcodeDescription());
         }
         else
         {
            Print("BUY STOP: ", DoubleToString(newPrice, _Digits), " SL=", DoubleToString(newSL, _Digits));
            LogTrade("BUY STOP: " + DoubleToString(newPrice, _Digits));
         }
      }
      else if(hedgeType == ORDER_TYPE_BUY_STOP)
      {
         double curPP = OrderGetDouble(ORDER_PRICE_OPEN);
         double curPS = OrderGetDouble(ORDER_SL);
         
         double askPrice = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
         double freezeLevel = MathMax(10, SymbolInfoInteger(Symbol(), SYMBOL_TRADE_FREEZE_LEVEL)) * point;
         if(MathAbs(askPrice - curPP) <= freezeLevel) return;
         
         double threshold = ModifyThreshold * point;
         if(MathAbs(curPP - newPrice) > threshold || MathAbs(curPS - newSL) > threshold)
         {
            ResetLastError();
            if(!trade.OrderModify(hedgeTicket, newPrice, newSL, 0, ORDER_TIME_GTC, 0))
            {
               int err = GetLastError();
               if(err != 10004 && err != 4756)
                  Print("ERROR mod BUY STOP: ", trade.ResultRetcodeDescription());
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Display Info                                                     |
//+------------------------------------------------------------------+
void DisplayInfo()
{
   if(!ShowInfo) return;
   
   int positions = CountMainOrders();
   int pending = CountPendingOrders();
   double totalProfit = 0;
   string info = "\n=== EA HFT v3.00 UNIVERSAL ===\n";
   info += "Symbol: " + Symbol() + " | Digits: " + IntegerToString(_Digits) + "\n";
   info += "Positions: " + IntegerToString(positions) + " | Pending: " + IntegerToString(pending) + "\n";
   
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == Magic)
         totalProfit += PositionGetDouble(POSITION_PROFIT);
   }
   
   info += "Profit: " + DoubleToString(totalProfit, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) + "\n";
   
   if(UseAutoLot)
      info += "AutoLot: " + DoubleToString(CalculateAutoLot(), 2) + " (" + DoubleToString(RiskPercent, 1) + "% Eq)\n";
   
   if(UseDailyLossLimit && g_AdjustedDailyLoss > 0)
   {
      double dp = GetDailyProfit();
      info += "Daily: " + DoubleToString(dp, 2);
      info += (dp <= -g_AdjustedDailyLoss ? " [LIMIT!]" : " (Lim:" + DoubleToString(-g_AdjustedDailyLoss, 2) + ")") + "\n";
   }
   
   if(UseMaxDrawdown && MaxDrawdownPercent > 0 && g_InitialBalance > 0)
   {
      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      double dd = ((g_InitialBalance - eq) / g_InitialBalance) * 100.0;
      info += "DD: " + DoubleToString(dd, 2) + "%";
      info += (dd >= MaxDrawdownPercent ? " [CRIT!]" : dd >= MaxDrawdownPercent*0.75 ? " [WARN!]" : " (Max:" + DoubleToString(MaxDrawdownPercent, 2) + "%)") + "\n";
   }
   
   if(g_TradingStopped) info += "STATUS: STOPPED\n";
   
   info += "Session: " + GetCurrentSessionName() + (!IsSessionAllowed() ? " [PAUSED]" : "") + "\n";
   info += "Spread: " + IntegerToString(SymbolInfoInteger(Symbol(), SYMBOL_SPREAD)) + " pts" + (MaxSpread > 0 ? " (Max:" + IntegerToString(MaxSpread) + ")" : "") + "\n";
   
   double ml = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(ml > 0) info += "Margin: " + DoubleToString(ml, 2) + "%" + (MinMarginLevel > 0 ? " (Min:" + DoubleToString(MinMarginLevel, 2) + "%)" : "") + "\n";
   
   if(g_IsCentAccount) info += "[CENT ACCOUNT]\n";
   
   Comment(info);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!CheckMaxDrawdown()) return;
   
   if(!CheckDailyLossLimit())
   {
      DisplayInfo();
      return;
   }
   
   TrailOrders();
   HandlePending();

   if(!g_TradingStopped && IsSessionAllowed() && CountMainOrders() == 0 && CountPendingOrders() == 0)
   {
      if(StartDirection == 0)
         OpenMainOrder(ORDER_TYPE_BUY);
      else
         OpenMainOrder(ORDER_TYPE_SELL);
   }
   
   DisplayInfo();
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(ShowInfo) Comment("");
   Print("EA HFT v3.00 Stopped. Reason: ", reason);
   LogTrade("EA stopped. Reason: " + IntegerToString(reason));
}