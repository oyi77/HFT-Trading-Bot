//+------------------------------------------------------------------+
//|                                            Maybe HFT no LOCK.mq5 |
//|                                                         Mas Imam |
//|                                              wa.me/6289679369219 |
//+------------------------------------------------------------------+
#property copyright "Mas Imam"
#property link      "wa.me/6289679369219"
#property version   "2.10"
//+------------------------------------------------------------------+
//| Hedging EA - Main + Hedge (Max 2 positions, Pending follow SL)   |
//| MT5 Version - IMPROVED with Error Handling & Risk Management     |
//| Added: Daily Loss Limit, Max Drawdown, Break Even                |
//+------------------------------------------------------------------+
#property strict

//--- Trading Parameters
input double   Lots        = 0.10;
input int      StopLoss    = 1500;   // SL dalam point
input int      TakeProfit  = 0;      // TP dalam point (0 = tidak pakai TP, hanya trailing)
input int      Trailing    = 500;    // jarak trailing dalam point
input int      TrailStart  = 1000;   // minimal profit (point) sebelum trailing aktif
input int      XDistance   = 300;    // jarak pending dari SL
input int      Slippage    = 30;
input int      Magic       = 12345;
input int      StartDirection = 0;   // 0=BUY pertama, 1=SELL pertama

//--- Risk Management Parameters
input int      MaxSpread   = 50;     // maksimal spread dalam point (0 = tidak check)
input double   MinMarginLevel = 200.0; // minimal margin level dalam % (0 = tidak check)
input int      ModifyThreshold = 2;   // threshold untuk modify pending (dalam point)

//--- Daily Loss Limit & Drawdown Protection
input bool     UseDailyLossLimit = true;  // Enable daily loss limit
input double   MaxDailyLoss = 100.0;     // Maksimal loss harian dalam currency (0 = tidak check)
input bool     StopTradingOnLossLimit = true; // Stop trading jika mencapai loss limit
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

//+------------------------------------------------------------------+
//| Normalize Price                                                  |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize > 0)
      return NormalizeDouble(MathRound(price / tickSize) * tickSize, _Digits);
   return NormalizeDouble(price, _Digits);
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
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   trade.SetAsyncMode(false);
   
   //--- Initialize Global Variables
   if(InitialBalance > 0)
      g_InitialBalance = InitialBalance;
   else
      g_InitialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   g_LastDayCheck = 0;
   g_TradingStopped = false;
   
   //--- Validate Risk Management Parameters
   if(UseDailyLossLimit && MaxDailyLoss <= 0)
   {
      Print("WARNING: UseDailyLossLimit is true but MaxDailyLoss is 0 or negative. Disabling daily loss limit.");
   }
   
   if(UseMaxDrawdown && MaxDrawdownPercent <= 0)
   {
      Print("WARNING: UseMaxDrawdown is true but MaxDrawdownPercent is 0 or negative. Disabling max drawdown protection.");
   }
   
   if(UseBreakEven && BreakEvenProfit <= 0)
   {
      Print("WARNING: UseBreakEven is true but BreakEvenProfit is 0 or negative. Disabling break even.");
   }
   
   //--- Display Info
   if(ShowInfo)
   {
      Comment("EA HFT Initialized\n",
              "Symbol: ", Symbol(), "\n",
              "Lots: ", Lots, "\n",
              "StopLoss: ", StopLoss, " points\n",
              "Magic: ", Magic, "\n",
              "Initial Balance: ", DoubleToString(g_InitialBalance, 2));
   }
   
   Print("EA HFT Initialized Successfully");
   Print("Parameters: Lots=", Lots, ", SL=", StopLoss, ", Trailing=", Trailing, ", TrailStart=", TrailStart);
   Print("Risk Management: Daily Loss Limit=", (UseDailyLossLimit ? DoubleToString(MaxDailyLoss, 2) : "OFF"),
         ", Max Drawdown=", (UseMaxDrawdown ? DoubleToString(MaxDrawdownPercent, 2) + "%" : "OFF"),
         ", Break Even=", (UseBreakEven ? "ON" : "OFF"));
   
//+------------------------------------------------------------------+
//| Setup Trade                                                      |
//+------------------------------------------------------------------+

return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Check Spread                                                      |
//+------------------------------------------------------------------+
bool CheckSpread()
{
   if(MaxSpread <= 0) return true; // Skip check if MaxSpread = 0
   
   long spread = SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
   if(spread > MaxSpread)
   {
      if(EnableLogging)
         Print("Spread too wide: ", spread, " points (Max: ", MaxSpread, ")");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Check Margin                                                      |
//+------------------------------------------------------------------+
bool CheckMargin(double requiredLots = 0)
{
   if(MinMarginLevel <= 0) return true; // Skip check if MinMarginLevel = 0
   
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(marginLevel > 0 && marginLevel < MinMarginLevel)
   {
      if(EnableLogging)
         Print("Margin level too low: ", DoubleToString(marginLevel, 2), "% (Min: ", DoubleToString(MinMarginLevel, 2), "%)");
      return false;
   }
   
   // Check free margin
   if(requiredLots > 0)
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double marginRequired = requiredLots * SymbolInfoDouble(Symbol(), SYMBOL_MARGIN_INITIAL);
      if(freeMargin < marginRequired * 2)
      {
         if(EnableLogging)
            Print("Insufficient free margin. Required: ", DoubleToString(marginRequired * 2, 2), ", Available: ", DoubleToString(freeMargin, 2));
         return false;
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
//| Get Daily Profit (from positions and history)                     |
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
   
   //--- Calculate profit from open positions opened today
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && 
         PositionGetInteger(POSITION_MAGIC) == Magic)
      {
         datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
         if(openTime >= todayStart)
            totalProfit += PositionGetDouble(POSITION_PROFIT);
      }
   }
   
   //--- Calculate profit from closed deals today
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
   if(!UseDailyLossLimit || MaxDailyLoss <= 0) return true;
   
   //--- Check if new day (reset check)
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime currentDay = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   
   if(currentDay != g_LastDayCheck)
   {
      g_LastDayCheck = currentDay;
      g_TradingStopped = false; // Reset trading stopped flag for new day
   }
   
   if(g_TradingStopped) return false;
   
   double dailyProfit = GetDailyProfit();
   
   if(dailyProfit <= -MaxDailyLoss)
   {
      string message = "Daily loss limit reached: " + DoubleToString(dailyProfit, 2) + 
                       " (Limit: " + DoubleToString(-MaxDailyLoss, 2) + ")";
      Print("WARNING: ", message);
      LogTrade("WARNING: " + message);
      
      if(StopTradingOnLossLimit)
      {
         g_TradingStopped = true;
         Print("Trading stopped due to daily loss limit.");
         LogTrade("Trading stopped due to daily loss limit.");
         return false;
      }
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Check Maximum Drawdown                                            |
//+------------------------------------------------------------------+
bool CheckMaxDrawdown()
{
   if(!UseMaxDrawdown || MaxDrawdownPercent <= 0) return true;
   
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   if(g_InitialBalance <= 0)
   {
      g_InitialBalance = currentBalance;
      return true;
   }
   
   double drawdownAmount = g_InitialBalance - currentBalance;
   double drawdownPercent = (drawdownAmount / g_InitialBalance) * 100.0;
   
   if(drawdownPercent >= MaxDrawdownPercent)
   {
      string message = "Maximum drawdown reached: " + DoubleToString(drawdownPercent, 2) + 
                       "% (Limit: " + DoubleToString(MaxDrawdownPercent, 2) + "%)";
      Print("CRITICAL: ", message);
      LogTrade("CRITICAL: " + message);
      
      Print("Stopping EA due to maximum drawdown protection.");
      LogTrade("EA stopped due to maximum drawdown protection.");
      ExpertRemove();
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Hitung order aktif (positions)                                    |
//+------------------------------------------------------------------+
int CountMainOrders()
{
   int count=0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol())
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic)
            count++;
      }
   }
   return(count);
}

//--- hitung pending orders
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
//| Buka order utama                                                 |
//+------------------------------------------------------------------+
void OpenMainOrder(int direction)
{
   //--- Check Spread
   if(!CheckSpread())
   {
      LogTrade("Cannot open order: Spread too wide");
      return;
   }
   
   //--- Check Margin
   if(!CheckMargin(Lots))
   {
      LogTrade("Cannot open order: Insufficient margin");
      return;
   }
   
   double price, sl, tp = 0;
   double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   
   if(point <= 0)
   {
      Print("ERROR: Invalid point value for ", Symbol());
      return;
   }
   
   if(direction == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      if(price <= 0)
      {
         Print("ERROR: Invalid ASK price for ", Symbol());
         return;
      }
      
      sl = NormalizePrice(price - StopLoss * point);
      if(TakeProfit > 0)
         tp = NormalizePrice(price + TakeProfit * point);
      
      //--- Validate SL
      double minStopLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL) * point;
      if(minStopLevel > 0 && (price - sl) < minStopLevel)
      {
         Print("ERROR: StopLoss too close. Min stop level: ", minStopLevel, " points");
         return;
      }
      
      //--- Open BUY Order
      if(!trade.Buy(Lots, Symbol(), price, sl, tp, "Main BUY"))
      {
         int error = GetLastError();
         string errorDesc = trade.ResultRetcodeDescription();
         Print("ERROR opening BUY: Code=", error, ", Description=", errorDesc);
         LogTrade("ERROR opening BUY: " + errorDesc);
      }
      else
      {
         Print("SUCCESS: BUY order opened at ", price, ", SL=", sl, (tp > 0 ? ", TP=" + DoubleToString(tp, 5) : ""));
         LogTrade("BUY order opened: Price=" + DoubleToString(price, 5) + ", SL=" + DoubleToString(sl, 5));
      }
   }
   else if(direction == ORDER_TYPE_SELL)
   {
      price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      if(price <= 0)
      {
         Print("ERROR: Invalid BID price for ", Symbol());
         return;
      }
      
      sl = NormalizePrice(price + StopLoss * point);
      if(TakeProfit > 0)
         tp = NormalizePrice(price - TakeProfit * point);
      
      //--- Validate SL
      double minStopLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL) * point;
      if(minStopLevel > 0 && (sl - price) < minStopLevel)
      {
         Print("ERROR: StopLoss too close. Min stop level: ", minStopLevel, " points");
         return;
      }
      
      //--- Open SELL Order
      if(!trade.Sell(Lots, Symbol(), price, sl, tp, "Main SELL"))
      {
         int error = GetLastError();
         string errorDesc = trade.ResultRetcodeDescription();
         Print("ERROR opening SELL: Code=", error, ", Description=", errorDesc);
         LogTrade("ERROR opening SELL: " + errorDesc);
      }
      else
      {
         Print("SUCCESS: SELL order opened at ", price, ", SL=", sl, (tp > 0 ? ", TP=" + DoubleToString(tp, 5) : ""));
         LogTrade("SELL order opened: Price=" + DoubleToString(price, 5) + ", SL=" + DoubleToString(sl, 5));
      }
   }
}

//+------------------------------------------------------------------+
//| Trailing order dengan syarat profit > TrailStart                 |
//| Includes Break Even Function                                      |
//+------------------------------------------------------------------+
void TrailOrders()
{
   double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   if(point <= 0) return;
   
   double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return;
   
   double minStopLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL) * point;
   
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol())
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic)
         {
            ulong ticket = PositionGetInteger(POSITION_TICKET);
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            double stopLoss = PositionGetDouble(POSITION_SL);
            double takeProfit = PositionGetDouble(POSITION_TP);
            ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            
            if(posType == POSITION_TYPE_BUY)
            {
               double profitPoints = (bid - openPrice) / point;
               double newSL = stopLoss;
               bool needModify = false;
               
               //--- Break Even Function (before trailing)
               if(UseBreakEven && BreakEvenProfit > 0 && 
                  profitPoints >= BreakEvenProfit && profitPoints < TrailStart)
               {
                  // Move SL to break even + offset
                  newSL = openPrice + (BreakEvenOffset * point);
                  
                   //--- Validate new SL
                   if(minStopLevel > 0 && (bid - newSL) < minStopLevel)
                   {
                      newSL = bid - minStopLevel;
                   }
                   
                   newSL = NormalizePrice(newSL);
                   
                   if(newSL > stopLoss && newSL < bid - (minStopLevel))
                   {
                      needModify = true;
                      if(EnableLogging)
                         LogTrade("Break Even: Moving BUY SL to " + DoubleToString(newSL, 5));
                   }
               }
               //--- Trailing Stop (after TrailStart)
               else if(profitPoints > TrailStart)
               {
                  newSL = bid - Trailing * point;
                  
                  //--- Validate new SL
                  if(minStopLevel > 0 && (bid - newSL) < minStopLevel)
                  {
                     newSL = bid - minStopLevel;
                  }
                  
                  if(newSL > stopLoss && newSL < bid)
                  {
                     needModify = true;
                  }
               }
               
               //--- Modify if needed
               if(needModify)
               {
                  if(!trade.PositionModify(ticket, newSL, takeProfit))
                  {
                     int error = GetLastError();
                     if(error != 10004) // Not "No error" but "Requote"
                     {
                        Print("ERROR modifying BUY SL: Code=", error, ", Description=", trade.ResultRetcodeDescription());
                     }
                  }
               }
            }
            else if(posType == POSITION_TYPE_SELL)
            {
               double profitPoints = (openPrice - ask) / point;
               double newSL = stopLoss;
               bool needModify = false;
               
               //--- Break Even Function (before trailing)
               if(UseBreakEven && BreakEvenProfit > 0 && 
                  profitPoints >= BreakEvenProfit && profitPoints < TrailStart)
               {
                  // Move SL to break even - offset
                  newSL = openPrice - (BreakEvenOffset * point);
                  
                   //--- Validate new SL
                   if(minStopLevel > 0 && (newSL - ask) < minStopLevel)
                   {
                      newSL = ask + minStopLevel;
                   }
                   
                   newSL = NormalizePrice(newSL);
                   
                   if((newSL < stopLoss || stopLoss == 0) && newSL > ask + (minStopLevel))
                   {
                      needModify = true;
                      if(EnableLogging)
                         LogTrade("Break Even: Moving SELL SL to " + DoubleToString(newSL, 5));
                   }
               }
               //--- Trailing Stop (after TrailStart)
               else if(profitPoints > TrailStart)
               {
                  newSL = ask + Trailing * point;
                  
                  //--- Validate new SL
                  if(minStopLevel > 0 && (newSL - ask) < minStopLevel)
                  {
                     newSL = ask + minStopLevel;
                  }
                  
                  if((newSL < stopLoss || stopLoss == 0) && newSL > ask)
                  {
                     needModify = true;
                  }
               }
               
               //--- Modify if needed
               if(needModify)
               {
                  if(!trade.PositionModify(ticket, newSL, takeProfit))
                  {
                     int error = GetLastError();
                     if(error != 10004) // Not "No error" but "Requote"
                     {
                        Print("ERROR modifying SELL SL: Code=", error, ", Description=", trade.ResultRetcodeDescription());
                     }
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Handle pending (buat/modify)                                    |
//+------------------------------------------------------------------+
void HandlePending()
{
   //--- Check Spread
   if(!CheckSpread()) return;
   
   //--- Check Margin
   if(!CheckMargin(Lots)) return;
   
   ENUM_POSITION_TYPE mainType = -1;
   double mainSL = 0;
   ulong hedgeTicket = 0;
   ENUM_ORDER_TYPE hedgeType = -1;
   double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   
   if(point <= 0) return;

   double newPrice = 0, newSL = 0;


   //--- Cari posisi utama
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol())
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic)
         {
            mainType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            mainSL = PositionGetDouble(POSITION_SL);
            break;
         }
      }
   }
   
   //--- Cari pending order
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
      
      //--- Validate newPrice against current price
      if(newPrice > currentPrice - minDistance)
         newPrice = currentPrice - minDistance - point;
         
      newSL = newPrice + StopLoss * point;
      
      newPrice = NormalizePrice(newPrice);
      newSL = NormalizePrice(newSL);
      
      if(hedgeTicket == 0)
      {
         //--- Create new SELL STOP pending
         if(!trade.SellStop(Lots, newPrice, Symbol(), newSL, 0, ORDER_TIME_GTC, 0, "Hedge SELL STOP"))
         {
            int error = GetLastError();
            string errorDesc = trade.ResultRetcodeDescription();
            Print("ERROR creating SELL STOP pending: Code=", error, ", Description=", errorDesc);
            LogTrade("ERROR creating SELL STOP: " + errorDesc);
         }
         else
         {
            Print("SUCCESS: SELL STOP pending created at ", newPrice, ", SL=", newSL);
            LogTrade("SELL STOP pending created: Price=" + DoubleToString(newPrice, 5) + ", SL=" + DoubleToString(newSL, 5));
         }
      }
      else if(hedgeType == ORDER_TYPE_SELL_STOP)
      {
         double currentPendingPrice = OrderGetDouble(ORDER_PRICE_OPEN);
         double currentPendingSL = OrderGetDouble(ORDER_SL);
         
         double threshold = ModifyThreshold * point;
         if(MathAbs(currentPendingPrice - newPrice) > threshold || MathAbs(currentPendingSL - newSL) > threshold)
         {
            if(!trade.OrderModify(hedgeTicket, newPrice, newSL, 0, ORDER_TIME_GTC, 0))
            {
               int error = GetLastError();
               if(error != 10004) // Not "No error" but "Requote"
               {
                  Print("ERROR modifying SELL STOP pending: Code=", error, ", Description=", trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
   else if(mainType == POSITION_TYPE_SELL && mainSL > 0)
   {
      newPrice = mainSL - XDistance * point;
      
      //--- Validate newPrice against current price
      if(newPrice < currentPrice + minDistance)
         newPrice = currentPrice + minDistance + point;
         
      newSL = newPrice - StopLoss * point;
      
      newPrice = NormalizePrice(newPrice);
      newSL = NormalizePrice(newSL);
      
      if(hedgeTicket == 0)
      {
         //--- Create new BUY STOP pending
         if(!trade.BuyStop(Lots, newPrice, Symbol(), newSL, 0, ORDER_TIME_GTC, 0, "Hedge BUY STOP"))
         {
            int error = GetLastError();
            string errorDesc = trade.ResultRetcodeDescription();
            Print("ERROR creating BUY STOP pending: Code=", error, ", Description=", errorDesc);
            LogTrade("ERROR creating BUY STOP: " + errorDesc);
         }
         else
         {
            Print("SUCCESS: BUY STOP pending created at ", newPrice, ", SL=", newSL);
            LogTrade("BUY STOP pending created: Price=" + DoubleToString(newPrice, 5) + ", SL=" + DoubleToString(newSL, 5));
         }
      }
      else if(hedgeType == ORDER_TYPE_BUY_STOP)
      {
         double currentPendingPrice = OrderGetDouble(ORDER_PRICE_OPEN);
         double currentPendingSL = OrderGetDouble(ORDER_SL);
         
         double threshold = ModifyThreshold * point;
         if(MathAbs(currentPendingPrice - newPrice) > threshold || MathAbs(currentPendingSL - newSL) > threshold)
         {
            if(!trade.OrderModify(hedgeTicket, newPrice, newSL, 0, ORDER_TIME_GTC, 0))
            {
               int error = GetLastError();
               if(error != 10004) // Not "No error" but "Requote"
               {
                  Print("ERROR modifying BUY STOP pending: Code=", error, ", Description=", trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Display Info di Chart                                            |
//+------------------------------------------------------------------+
void DisplayInfo()
{
   if(!ShowInfo) return;
   
   int positions = CountMainOrders();
   int pending = CountPendingOrders();
   double totalProfit = 0;
   string info = "\n=== EA HFT Status ===\n";
   info += "Symbol: " + Symbol() + "\n";
   info += "Positions: " + IntegerToString(positions) + "\n";
   info += "Pending: " + IntegerToString(pending) + "\n";
   
   //--- Calculate total profit
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(PositionGetSymbol(i) == Symbol())
      {
         if(PositionGetInteger(POSITION_MAGIC) == Magic)
         {
            totalProfit += PositionGetDouble(POSITION_PROFIT);
         }
      }
   }
   
   info += "Profit: " + DoubleToString(totalProfit, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) + "\n";
   
   //--- Daily Profit/Loss
   if(UseDailyLossLimit && MaxDailyLoss > 0)
   {
      double dailyProfit = GetDailyProfit();
      info += "Daily P/L: " + DoubleToString(dailyProfit, 2);
      if(dailyProfit <= -MaxDailyLoss)
         info += " [LIMIT REACHED!]";
      else
         info += " (Limit: " + DoubleToString(-MaxDailyLoss, 2) + ")";
      info += "\n";
   }
   
   //--- Drawdown Info
   if(UseMaxDrawdown && MaxDrawdownPercent > 0 && g_InitialBalance > 0)
   {
      double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      double drawdownPercent = ((g_InitialBalance - currentBalance) / g_InitialBalance) * 100.0;
      info += "Drawdown: " + DoubleToString(drawdownPercent, 2) + "%";
      if(drawdownPercent >= MaxDrawdownPercent)
         info += " [CRITICAL!]";
      else
         info += " (Max: " + DoubleToString(MaxDrawdownPercent, 2) + "%)";
      info += "\n";
   }
   
   //--- Trading Status
   if(g_TradingStopped)
   {
      info += "STATUS: TRADING STOPPED (Daily Loss Limit)\n";
   }
   
   //--- Spread info
   long spread = SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
   info += "Spread: " + IntegerToString(spread) + " points";
   if(MaxSpread > 0)
      info += " (Max: " + IntegerToString(MaxSpread) + ")";
   info += "\n";
   
   //--- Margin info
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(marginLevel > 0)
   {
      info += "Margin Level: " + DoubleToString(marginLevel, 2) + "%";
      if(MinMarginLevel > 0)
         info += " (Min: " + DoubleToString(MinMarginLevel, 2) + "%)";
      info += "\n";
   }
   
   Comment(info);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Check Maximum Drawdown (critical - check first)
   if(!CheckMaxDrawdown())
      return; // EA will be removed by CheckMaxDrawdown()
   
   //--- Check Daily Loss Limit
   if(!CheckDailyLossLimit())
   {
      // Trading stopped due to daily loss limit
      DisplayInfo();
      return;
   }
   
   //--- Update trailing stop (includes break even)
   TrailOrders();
   
   //--- Handle pending orders
   HandlePending();

   //--- Kalau tidak ada posisi sama sekali, buka main sesuai StartDirection
   if(!g_TradingStopped && CountMainOrders() == 0 && CountPendingOrders() == 0)
   {
      if(StartDirection == 0)
         OpenMainOrder(ORDER_TYPE_BUY);
      else
         OpenMainOrder(ORDER_TYPE_SELL);
   }
   
   //--- Display info
   DisplayInfo();
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(ShowInfo)
      Comment("");
   
   Print("EA HFT Deinitialized. Reason: ", reason);
   LogTrade("EA HFT Deinitialized. Reason: " + IntegerToString(reason));
}