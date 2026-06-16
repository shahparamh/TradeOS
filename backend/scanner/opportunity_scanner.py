class OpportunityScanner:
    def scan_all(self, watchlist_data: list[dict], news_data: dict, fundamentals: dict, derivatives: dict = None) -> list[dict]:
        opportunities = []
        for stock in watchlist_data:
            # Skip if error
            if "error" in stock:
                continue
                
            results = []
            symbol = stock["symbol"]
            stock_news = news_data.get(symbol, [])
            stock_fund = fundamentals.get(symbol, {})
            stock_deriv = derivatives.get(symbol, {}) if derivatives else {}
            
            is_fno = symbol.startswith("^") or symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]
            
            if is_fno:
                # F&O specific scanner logic
                results.extend(self.scan_momentum_breakout(stock))
                results.extend(self.scan_bearish_breakdown(stock, stock_news))
                results.extend(self.scan_mean_reversion(stock))
                results.extend(self.scan_price_action(stock))
                results.extend(self.scan_fno_derivatives(stock, stock_deriv))
            else:
                # Equity specific scanner logic
                results.extend(self.scan_momentum_breakout(stock))
                results.extend(self.scan_bearish_breakdown(stock, stock_news))
                results.extend(self.scan_earnings_momentum(stock, stock_fund, stock_news))
                results.extend(self.scan_panic_selloff(stock, stock_news))
                results.extend(self.scan_mean_reversion(stock))
                results.extend(self.scan_price_action(stock))
            
            opportunities.extend(results)
            
        # Sort opportunities by strength
        # strong -> moderate -> weak
        def strength_score(opp):
            if opp["signal_strength"] == "strong": return 3
            if opp["signal_strength"] == "moderate": return 2
            return 1
            
        opportunities.sort(key=strength_score, reverse=True)
        return opportunities

    def scan_momentum_breakout(self, stock: dict) -> list[dict]:
        symbol = stock["symbol"]
        price = stock["price"]
        rsi = stock["rsi"]
        macd = stock["macd"]
        vol_ratio = stock["volume_ratio"]
        price_vs_ema20 = stock["price_vs_ema20"]
        price_vs_vwap = stock["price_vs_vwap"]

        is_index = symbol.startswith("^")
        vol_check = True if is_index else (vol_ratio > 1.5)
        vwap_check = True if is_index else (price_vs_vwap == "above")
        rsi_lower = 45 if is_index else 55
        rsi_upper = 85 if is_index else 80

        if (price_vs_ema20 == "above" and
            vwap_check and
            vol_check and
            rsi_lower < rsi < rsi_upper and
            macd == "bullish"):

            reasons = [
                f"Price above 20 EMA ({stock['ema_20']})",
                f"Price above VWAP ({stock['vwap']})" if not is_index else "Price in bullish trend (index)",
                f"Volume {vol_ratio}x average" if not is_index else "Volume check bypassed (index)",
                f"RSI at {rsi} (bullish momentum)",
                f"MACD bullish crossover"
            ]

            boosters = 0
            if stock["price_vs_ema50"] == "above":
                boosters += 1
                reasons.append(f"Price above 50 EMA ({stock['ema_50']})")
            if not is_index and vol_ratio > 2.5:
                boosters += 1
                reasons.append(f"Extreme volume spike ({vol_ratio}x)")

            strength = "strong" if boosters >= 1 else "moderate"

            return [{
                "symbol": symbol,
                "signal_type": "bullish_breakout",
                "signal_strength": strength,
                "suggested_action": "BUY",
                "suggested_position": "LONG",
                "reasons": reasons,
                "indicators": stock
            }]
        return []

    def scan_bearish_breakdown(self, stock: dict, news: list) -> list[dict]:
        symbol = stock["symbol"]
        is_index = symbol.startswith("^")
        vol_check = True if is_index else (stock["volume_ratio"] > 1.5)
        vwap_check = True if is_index else (stock["price_vs_vwap"] == "below")
        rsi_upper = 55 if is_index else 45

        if (stock["price_vs_ema20"] == "below" and
            vwap_check and
            vol_check and
            stock["rsi"] < rsi_upper and
            stock["macd"] == "bearish"):
            
            strength = "moderate"
            reasons = [
                "Price broke below 20 EMA and VWAP with volume" if not is_index else "Price broke below 20 EMA (index)"
            ]
            
            # Check news for negative sentiment
            has_negative_news = any(n.get("sentiment") == "negative" for n in news)
            if has_negative_news:
                strength = "strong"
                reasons.append("Negative news sentiment detected")
                
            return [{
                "symbol": stock["symbol"],
                "signal_type": "bearish_breakdown",
                "signal_strength": strength,
                "suggested_action": "SHORT",
                "suggested_position": "SHORT",
                "reasons": reasons,
                "indicators": stock
            }]
        return []

    def scan_earnings_momentum(self, stock: dict, fundamentals: dict, news: list) -> list[dict]:
        rev_growth = fundamentals.get("revenue_growth")
        profit_growth = fundamentals.get("profit_growth")
        
        if rev_growth and profit_growth:
            if rev_growth > 10 and profit_growth > 15 and stock["rsi"] > 50:
                return [{
                    "symbol": stock["symbol"],
                    "signal_type": "bullish_earnings_momentum",
                    "signal_strength": "strong",
                    "suggested_action": "BUY",
                    "suggested_position": "LONG",
                    "reasons": [
                        f"Strong revenue growth ({rev_growth}%)",
                        f"Strong profit growth ({profit_growth}%)"
                    ],
                    "indicators": stock
                }]
            elif rev_growth < 0 and profit_growth < -10 and stock["rsi"] < 50:
                return [{
                    "symbol": stock["symbol"],
                    "signal_type": "bearish_earnings_miss",
                    "signal_strength": "strong",
                    "suggested_action": "SHORT",
                    "suggested_position": "SHORT",
                    "reasons": [
                        f"Declining revenue ({rev_growth}%)",
                        f"Declining profit ({profit_growth}%)"
                    ],
                    "indicators": stock
                }]
        return []

    def scan_panic_selloff(self, stock: dict, news: list) -> list[dict]:
        if (stock["volume_ratio"] > 3.0 and
            stock["rsi"] < 30 and
            stock["bb_position"] == "oversold"):
            
            return [{
                "symbol": stock["symbol"],
                "signal_type": "panic_selloff",
                "signal_strength": "strong",
                "suggested_action": "BUY",
                "suggested_position": "LONG",
                "reasons": [
                    "Extreme oversold condition (RSI < 30)",
                    "Price below lower Bollinger Band",
                    "Panic volume detected"
                ],
                "indicators": stock
            }]
        return []

    def scan_mean_reversion(self, stock: dict) -> list[dict]:
        symbol = stock["symbol"]
        is_index = symbol.startswith("^")
        vol_check_oversold = True if is_index else (stock["volume_ratio"] < 1.0)
        vol_check_overbought = True if is_index else (stock["volume_ratio"] < 1.0)

        if stock["bb_position"] == "oversold" and stock["rsi"] < 35 and vol_check_oversold:
            return [{
                "symbol": stock["symbol"],
                "signal_type": "bullish_mean_reversion",
                "signal_strength": "moderate",
                "suggested_action": "BUY",
                "suggested_position": "LONG",
                "reasons": ["Price over-extended to downside" if is_index else "Price over-extended to downside, volume drying up"],
                "indicators": stock
            }]
        elif stock["bb_position"] == "overbought" and stock["rsi"] > 70 and vol_check_overbought:
            return [{
                "symbol": stock["symbol"],
                "signal_type": "bearish_mean_reversion",
                "signal_strength": "moderate",
                "suggested_action": "SHORT",
                "suggested_position": "SHORT",
                "reasons": ["Price over-extended to upside" if is_index else "Price over-extended to upside, volume drying up"],
                "indicators": stock
            }]
        return []

    def scan_price_action(self, stock: dict) -> list[dict]:
        symbol = stock["symbol"]
        price = stock["price"]
        rsi = stock["rsi"]
        pattern = stock.get("candlestick_pattern", "None")
        vol_ratio = stock.get("volume_ratio", 1.0)
        
        # Bullish Price Action: Hammer or Bullish Engulfing near support / oversold zone
        if pattern in ["Hammer", "Bullish Engulfing"]:
            if rsi < 45 or stock["bb_position"] == "oversold" or price <= stock.get("support_1", 0) * 1.01:
                return [{
                    "symbol": symbol,
                    "signal_type": "bullish_price_action",
                    "signal_strength": "strong" if vol_ratio > 1.2 else "moderate",
                    "suggested_action": "BUY",
                    "suggested_position": "LONG",
                    "reasons": [
                        f"Bullish price action pattern detected: {pattern}",
                        "Price is located near key support or in oversold zone",
                        f"RSI is at {rsi}"
                    ],
                    "indicators": stock
                }]
                
        # Bearish Price Action: Bearish Engulfing near resistance / overbought zone
        if pattern == "Bearish Engulfing":
            if rsi > 55 or stock["bb_position"] == "overbought" or price >= stock.get("resistance_1", 0) * 0.99:
                return [{
                    "symbol": symbol,
                    "signal_type": "bearish_price_action",
                    "signal_strength": "strong" if vol_ratio > 1.2 else "moderate",
                    "suggested_action": "SHORT",
                    "suggested_position": "SHORT",
                    "reasons": [
                        f"Bearish price action pattern detected: {pattern}",
                        "Price is located near key resistance or in overbought zone",
                        f"RSI is at {rsi}"
                    ],
                    "indicators": stock
                }]
        return []

    def scan_fno_derivatives(self, stock: dict, derivatives: dict) -> list[dict]:
        symbol = stock["symbol"]
        pcr = derivatives.get("oi_pcr", 1.0)
        sentiment = derivatives.get("oi_sentiment", "NEUTRAL")
        
        # Bullish F&O Setup: PCR is bullish (support floor) and technical trend is bullish
        if pcr >= 1.15 and stock.get("trend") in ["strong_bullish", "bullish"]:
            return [{
                "symbol": symbol,
                "signal_type": "bullish_fno_trend",
                "signal_strength": "strong" if pcr >= 1.3 else "moderate",
                "suggested_action": "BUY",
                "suggested_position": "BUY_CE",
                "reasons": [
                    f"Bullish Put-Call Ratio (PCR: {pcr}) indicates strong support floor",
                    f"Technical trend is {stock.get('trend')}",
                    f"Option chain sentiment is {sentiment}"
                ],
                "indicators": stock
            }]
            
        # Bearish F&O Setup: PCR is bearish (heavy resistance) and technical trend is bearish
        if pcr <= 0.75 and stock.get("trend") in ["strong_bearish", "bearish"]:
            return [{
                "symbol": symbol,
                "signal_type": "bearish_fno_trend",
                "signal_strength": "strong" if pcr <= 0.6 else "moderate",
                "suggested_action": "SHORT",
                "suggested_position": "BUY_PE",
                "reasons": [
                    f"Bearish Put-Call Ratio (PCR: {pcr}) indicates heavy overhead resistance",
                    f"Technical trend is {stock.get('trend')}",
                    f"Option chain sentiment is {sentiment}"
                ],
                "indicators": stock
            }]
        return []
