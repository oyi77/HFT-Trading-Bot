//+------------------------------------------------------------------+
//|                                                ZeroLagEA_V2.mq5  |
//|                             Ahox Nugroho Strict Implementation   |
//+------------------------------------------------------------------+
#property copyright "ZeroLag V2"
#property link      ""
#property version   "2.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Input Group: Strategy Core (ZeroLag)
input group "Indicator Settings (ZeroLag Pine)"
input int    InpBandLength       = 63;     // Band Length
input double InpBandMultiplier   = 1.1;    // Band Multiplier

//--- Input Group: Risk & Grid 
input group "Grid & Pyramiding Logic"
input double InpBaseLot          = 0.01;   // Base Order Lot Size
input double InpLotMultiplier    = 2.0;    // Recovery Lot Multiplier (Martingale)
input double InpLayerGapPips     = 20.0;   // Jarak Averaging (Pips)
input int    InpMaxLayers        = 4;      // Max Maksimal Layer (Peluru)

//--- Input Group: Target Management (Ahox Rules)
input group "Take Profit & Runner Management"
input double InpTargetBasePips   = 30.0;   // Minimum TP Pips (30-50 XAU / 10 Forex)
input double InpRunnerTargetPips = 100.0;  // Runner Max Target Pips (100-300 Pip)
input bool   InpUseRunnerSys     = true;   // Use 2/3 Partial + Runner SL+ System?

//--- Input Group: News Filter (Forex Factory)
input group "News Filter (Forex Factory API)"
input bool   InpUseNewsFilter    = true;   // Use News Filter?
input string InpNewsCurrencies   = "USD,EUR,GBP,JPY,AUD,NZD,CAD,CHF,XAU"; 
input bool   InpBlockHighNews    = true;   // Block High Impact
input int    InpMinutesBeforeNews = 30;    // Pause Before News (Minutes)
input int    InpMinutesAfterNews  = 30;    // Pause After News (Minutes)

//--- Input Group: Time Filters
input group "Time Filters (Broker Time)"
input bool   InpUseTimeFilter    = true;   // Gunakan Filter Jam?
input int    InpSess1_Start      = 8;      // Sesi Pagi Mulai (08:00)
input int    InpSess1_End        = 12;     // Sesi Pagi Selesai (12:00)
input int    InpSess2_Start      = 14;     // Sesi Siang Mulai (14:00)
input int    InpSess2_End        = 17;     // Sesi Siang Selesai (17:00)
input int    InpSess3_Start      = 22;     // Sesi Malam Mulai (22:00)
input int    InpSess3_End        = 2;      // Sesi Malam Selesai (02:00 Next Day)

//--- Global Variables
CTrade         trade;
CSymbolInfo    symb;
CPositionInfo  posinfo;
int            magic_number = 888200; // V2 Magic
int            atr_handle;

double         pip_size;
int            current_trend = 0; // 1 = Bullish, -1 = Bearish
datetime       last_trade_time = 0;

struct NewsEvent {
   datetime time;
   string impact;
   string country;
};

NewsEvent g_news[];
datetime g_last_news_fetch = 0;

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(magic_number);
   symb.Name(_Symbol);
   symb.Refresh();
   
   // Normalize pip size correctly for Forex (5 digits) vs Gold (2-3 digits)
   if(_Digits == 5 || _Digits == 3) pip_size = _Point * 10.0;
   else pip_size = _Point;
   
   atr_handle = iATR(_Symbol, _Period, InpBandLength);
   if(atr_handle == INVALID_HANDLE) {
      Print("Error creating ATR handle!");
      return INIT_FAILED;
   }
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(atr_handle != INVALID_HANDLE) IndicatorRelease(atr_handle);
}

//+------------------------------------------------------------------+
//| Process OnTick                                                   |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!symb.RefreshRates()) return;

   // 1. Calculate Zero Lag on every tick but only referencing completed Bars (index 1)
   CheckZeroLagSignal();

   // 2. Open first positions if valid
   ExecuteSignals();   

   // 3. Manage Pyramiding & TP Runner
   ManagePositions();
}

//+------------------------------------------------------------------+
//| Check Trading Hours                                              |
//+------------------------------------------------------------------+
bool IsTradingTime()
{
   if(!InpUseTimeFilter) return true;
   
   MqlDateTime dt;
   TimeCurrent(dt);
   int h = dt.hour;
   
   // Sess 1
   if(InpSess1_Start < InpSess1_End) {
      if(h >= InpSess1_Start && h < InpSess1_End) return true;
   } else {
      if(h >= InpSess1_Start || h < InpSess1_End) return true;
   }
   // Sess 2
   if(InpSess2_Start < InpSess2_End) {
      if(h >= InpSess2_Start && h < InpSess2_End) return true;
   } else {
      if(h >= InpSess2_Start || h < InpSess2_End) return true;
   }
   // Sess 3
   if(InpSess3_Start < InpSess3_End) {
      if(h >= InpSess3_Start && h < InpSess3_End) return true;
   } else {
      if(h >= InpSess3_Start || h < InpSess3_End) return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Update & Parse News (ForexFactory)                               |
//+------------------------------------------------------------------+
void UpdateNewsData()
{
   string url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json";
   char post[], result[];
   string headers;
   
   int res = WebRequest("GET", url, "", "", 5000, post, 0, result, headers);
   if(res == 200) {
       string json = CharArrayToString(result);
       ArrayResize(g_news, 0);
       
       int start_pos = 0;
       while(true) {
           int obj_start = StringFind(json, "{", start_pos);
           if(obj_start < 0) break;
           int obj_end = StringFind(json, "}", obj_start);
           if(obj_end < 0) break;
           
           string obj_str = StringSubstr(json, obj_start, obj_end - obj_start);
           
           // Country
           int c_pos = StringFind(obj_str, "\"country\":\"");
           string country = "";
           if(c_pos >= 0) {
               int c_end = StringFind(obj_str, "\"", c_pos + 11);
               country = StringSubstr(obj_str, c_pos + 11, c_end - (c_pos + 11));
           }
           
           // Impact
           int i_pos = StringFind(obj_str, "\"impact\":\"");
           string impact = "";
           if(i_pos >= 0) {
               int i_end = StringFind(obj_str, "\"", i_pos + 10);
               impact = StringSubstr(obj_str, i_pos + 10, i_end - (i_pos + 10));
           }
           
           // Date (UTC conversion)
           int d_pos = StringFind(obj_str, "\"date\":\"");
           datetime event_time = 0;
           if(d_pos >= 0) {
               int d_end = StringFind(obj_str, "\"", d_pos + 8);
               string date_str = StringSubstr(obj_str, d_pos + 8, d_end - (d_pos + 8));
               
               if(StringLen(date_str) >= 19) {
                   string year = StringSubstr(date_str, 0, 4);
                   string month = StringSubstr(date_str, 5, 2);
                   string day = StringSubstr(date_str, 8, 2);
                   string hour = StringSubstr(date_str, 11, 2);
                   string min = StringSubstr(date_str, 14, 2);
                   string sec = StringSubstr(date_str, 17, 2);
                   
                   event_time = StringToTime(year + "." + month + "." + day + " " + hour + ":" + min + ":" + sec);
                   
                   if(StringLen(date_str) >= 25) {
                       string auth_sign = StringSubstr(date_str, 19, 1);
                       string offset_h = StringSubstr(date_str, 20, 2);
                       string offset_m = StringSubstr(date_str, 23, 2);
                       
                       int offset_sec = (int)(StringToInteger(offset_h) * 3600 + StringToInteger(offset_m) * 60);
                       if(auth_sign == "-") offset_sec = -offset_sec;
                       else if(auth_sign == "+") offset_sec = offset_sec; 
                       
                       event_time = event_time - offset_sec; // Convert to UTC
                       event_time = event_time + (TimeCurrent() - TimeGMT()); // Convert to Broker Time
                   }
               }
           }
           
           if(country != "" && event_time > 0) {
               int size = ArraySize(g_news);
               ArrayResize(g_news, size + 1);
               g_news[size].time = event_time;
               g_news[size].impact = impact;
               g_news[size].country = country;
           }
           start_pos = obj_end + 1;
       }
   }
}

bool IsNewsTime()
{
   if(!InpUseNewsFilter) return false;
   
   if(TimeCurrent() - g_last_news_fetch > 12 * 3600) {
       UpdateNewsData();
       g_last_news_fetch = TimeCurrent();
   }
   
   if(ArraySize(g_news) == 0) return false;
   datetime now = TimeCurrent();
   
   for(int i = 0; i < ArraySize(g_news); i++) {
       if(InpBlockHighNews && g_news[i].impact == "High") {
           if(StringFind(InpNewsCurrencies, g_news[i].country) >= 0 || g_news[i].country == "USD") {
               datetime news_start = g_news[i].time - (InpMinutesBeforeNews * 60);
               datetime news_end = g_news[i].time + (InpMinutesAfterNews * 60);
               
               if(now >= news_start && now <= news_end) return true;
           }
       }
   }
   return false;
}

//+------------------------------------------------------------------+
//| ZeroLag Math Indicator Calculator                                |
//+------------------------------------------------------------------+
void CheckZeroLagSignal()
{
   int lag = (int)MathFloor((InpBandLength - 1.0) / 2.0);
   int calc_period = InpBandLength;
   int history_needed = calc_period + lag + 250; 
   
   double close[];
   ArraySetAsSeries(close, true);
   if(CopyClose(_Symbol, _Period, 0, history_needed, close) < history_needed) return;
   
   double custom_src[];
   ArrayResize(custom_src, history_needed - lag);
   ArraySetAsSeries(custom_src, true);
   
   for(int i = 0; i < history_needed - lag; i++) {
      custom_src[i] = close[i] + (close[i] - close[i+lag]);
   }
   
   double zlema[];
   ArrayResize(zlema, ArraySize(custom_src));
   ArraySetAsSeries(zlema, true);
   
   double k = 2.0 / (calc_period + 1.0);
   int start_idx = ArraySize(custom_src) - 1;
   
   zlema[start_idx] = custom_src[start_idx];
   for(int i = start_idx - 1; i >= 0; i--) {
      zlema[i] = custom_src[i] * k + zlema[i+1] * (1.0 - k);
   }
   
   double atr_val[];
   ArraySetAsSeries(atr_val, true);
   if(CopyBuffer(atr_handle, 0, 0, calc_period * 3 + 1, atr_val) <= 0) return;
   
   double highest_atr = 0;
   int atr_lookback = calc_period * 3;
   for(int i = 0; i < MathMin(atr_lookback, ArraySize(atr_val)); i++) {
      if(atr_val[i] > highest_atr) highest_atr = atr_val[i];
   }
   
   double volatility = highest_atr * InpBandMultiplier;
   
   // Strict Bar 1 signal parsing
   double current_zlema = zlema[1];  
   double current_close = close[1];
   double prev_zlema    = zlema[2];
   double prev_close    = close[2];
   
   // AHOX RULE: Cutloss on Reversal "Kalau signal berbalik... wajib keluar"
   if(prev_close <= prev_zlema + volatility && current_close > current_zlema + volatility) {
      if(current_trend != 1) {
         current_trend = 1;
         CloseAll(POSITION_TYPE_SELL); // Nuke opposite trends
      }
   } else if(prev_close >= prev_zlema - volatility && current_close < current_zlema - volatility) {
      if(current_trend != -1) {
         current_trend = -1;
         CloseAll(POSITION_TYPE_BUY); // Nuke opposite trends
      }
   }
}

//+------------------------------------------------------------------+
//| Initial Entry Logic (AHOX Rule: Close candle match Signal)       |
//+------------------------------------------------------------------+
void ExecuteSignals()
{
   if(!IsTradingTime() || IsNewsTime()) return;
   if(TimeCurrent() - last_trade_time < 3) return; 
   
   int buy_count = CountType(POSITION_TYPE_BUY);
   int sell_count = CountType(POSITION_TYPE_SELL);
   
   double open[];
   double close[];
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(close, true);
   CopyOpen(_Symbol, _Period, 0, 3, open);
   CopyClose(_Symbol, _Period, 0, 3, close);
   
   // Condition: Signal = Bullish (1), Bar 1 closed Green (Close > Open)
   if(current_trend == 1 && buy_count == 0 && sell_count == 0) {
      if(close[1] > open[1]) {
         trade.Buy(InpBaseLot, _Symbol, 0, 0, 0, "ZL Buy Entry");
         last_trade_time = TimeCurrent();
      }
   }
   
   // Condition: Signal = Bearish (-1), Bar 1 closed Red (Close < Open)
   if(current_trend == -1 && buy_count == 0 && sell_count == 0) {
      if(close[1] < open[1]) {
         trade.Sell(InpBaseLot, _Symbol, 0, 0, 0, "ZL Sell Entry");
         last_trade_time = TimeCurrent();
      }
   }
}

//+------------------------------------------------------------------+
//| Multiplier Grid & 2/3 Partial Close Runner                       |
//+------------------------------------------------------------------+
void ManagePositions()
{
   int total_buys = CountType(POSITION_TYPE_BUY);
   int total_sells = CountType(POSITION_TYPE_SELL);
   
   // ==========================================
   // BUY LOGIC
   // ==========================================
   if(total_buys > 0) {
       double lowest_buy = GetLowestPrice(POSITION_TYPE_BUY);
       double avg_price_buy = GetAveragePrice(POSITION_TYPE_BUY);
       
       // LAYER AVERAGING
       if(total_buys < InpMaxLayers && TimeCurrent() - last_trade_time >= 5) {
           if(symb.Ask() < lowest_buy - (InpLayerGapPips * pip_size)) {
               double next_lot = NormalizeDouble(InpBaseLot * MathPow(InpLotMultiplier, total_buys), 2);
               if(next_lot < 0.01) next_lot = 0.01;
               trade.Buy(next_lot, _Symbol, 0, 0, 0, "ZL Averaging Buy L"+IntegerToString(total_buys+1));
               last_trade_time = TimeCurrent();
           }
       }
       
       // BASKET TP RUNNER LOGIC
       if(symb.Bid() >= avg_price_buy + (InpTargetBasePips * pip_size)) {
           if(InpUseRunnerSys && total_buys > 1) {
               // AHOX RULE: If 4 layers, close bottom layers, BE top layers.
               ulong highest_buy_ticket = GetHighestPriceTicket(POSITION_TYPE_BUY);
               
               for(int i = PositionsTotal() - 1; i >= 0; i--) {
                   if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == POSITION_TYPE_BUY) {
                       if(posinfo.Ticket() == highest_buy_ticket) {
                           // Set SL to Break Even of the BASKET (AvgPrice + 5 pips)
                           double new_sl = avg_price_buy + (5.0 * pip_size);
                           double new_tp = avg_price_buy + (InpRunnerTargetPips * pip_size);
                           // Only modify if not already modified past this to avoid 130 error spam
                           if(posinfo.StopLoss() < new_sl || posinfo.TakeProfit() != new_tp) {
                               trade.PositionModify(posinfo.Ticket(), new_sl, new_tp);
                           }
                       } else {
                           trade.PositionClose(posinfo.Ticket()); // Take profit on all bottom layers!
                       }
                   }
               }
           } else {
               CloseAll(POSITION_TYPE_BUY); // Flat basket TP
           }
       }
       
       // HARD STOP LOSS DELETED
   }
   
   // ==========================================
   // SELL LOGIC
   // ==========================================
   if(total_sells > 0) {
       double highest_sell = GetHighestPrice(POSITION_TYPE_SELL);
       double avg_price_sell = GetAveragePrice(POSITION_TYPE_SELL);
       
       // LAYER AVERAGING
       if(total_sells < InpMaxLayers && TimeCurrent() - last_trade_time >= 5) {
           if(symb.Bid() > highest_sell + (InpLayerGapPips * pip_size)) {
               double next_lot = NormalizeDouble(InpBaseLot * MathPow(InpLotMultiplier, total_sells), 2);
               if(next_lot < 0.01) next_lot = 0.01;
               trade.Sell(next_lot, _Symbol, 0, 0, 0, "ZL Averaging Sell L"+IntegerToString(total_sells+1));
               last_trade_time = TimeCurrent();
           }
       }
       
       // BASKET TP RUNNER LOGIC
       if(symb.Ask() <= avg_price_sell - (InpTargetBasePips * pip_size)) {
           if(InpUseRunnerSys && total_sells > 1) {
               ulong lowest_sell_ticket = GetLowestPriceTicket(POSITION_TYPE_SELL);
               
               for(int i = PositionsTotal() - 1; i >= 0; i--) {
                   if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == POSITION_TYPE_SELL) {
                       if(posinfo.Ticket() == lowest_sell_ticket) {
                           // Set SL to Break Even of the BASKET (AvgPrice - 5 pips)
                           double new_sl = avg_price_sell - (5.0 * pip_size);
                           double new_tp = avg_price_sell - (InpRunnerTargetPips * pip_size);
                           if(posinfo.StopLoss() > new_sl || posinfo.StopLoss() == 0.0 || posinfo.TakeProfit() != new_tp) {
                               trade.PositionModify(posinfo.Ticket(), new_sl, new_tp);
                           }
                       } else {
                           trade.PositionClose(posinfo.Ticket());
                       }
                   }
               }
           } else {
               CloseAll(POSITION_TYPE_SELL);
           }
       }
       
       // HARD STOP LOSS DELETED
   }
}

//+------------------------------------------------------------------+
//| Utilities                                                        |
//+------------------------------------------------------------------+
void CloseAll(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i)) {
         if(posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
            trade.PositionClose(posinfo.Ticket());
         }
      }
   }
}

int CountType(ENUM_POSITION_TYPE type)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i)) {
         if(posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
            count++;
         }
      }
   }
   return count;
}

double GetAveragePrice(ENUM_POSITION_TYPE type)
{
    double total_volume = 0;
    double total_value = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
            total_volume += posinfo.Volume();
            total_value += posinfo.PriceOpen() * posinfo.Volume();
        }
    }
    if(total_volume > 0) return total_value / total_volume;
    return 0.0;
}

double GetLowestPrice(ENUM_POSITION_TYPE type)
{
   double lowest = 999999.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i)) {
         if(posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
            if(posinfo.PriceOpen() < lowest) lowest = posinfo.PriceOpen();
         }
      }
   }
   return lowest;
}

double GetHighestPrice(ENUM_POSITION_TYPE type)
{
   double highest = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i)) {
         if(posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
            if(posinfo.PriceOpen() > highest) highest = posinfo.PriceOpen();
         }
      }
   }
   return highest;
}

ulong GetHighestPriceTicket(ENUM_POSITION_TYPE type)
{
   double highest = 0.0;
   ulong ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
          if(posinfo.PriceOpen() > highest) {
              highest = posinfo.PriceOpen();
              ticket = posinfo.Ticket();
          }
      }
   }
   return ticket;
}

ulong GetLowestPriceTicket(ENUM_POSITION_TYPE type)
{
   double lowest = 999999.0;
   ulong ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(posinfo.SelectByIndex(i) && posinfo.Symbol() == _Symbol && posinfo.Magic() == magic_number && posinfo.PositionType() == type) {
          if(posinfo.PriceOpen() < lowest) {
              lowest = posinfo.PriceOpen();
              ticket = posinfo.Ticket();
          }
      }
   }
   return ticket;
}
