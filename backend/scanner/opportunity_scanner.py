class OpportunityScanner:
    def scan_all(self, watchlist_data: list[dict], news_data: dict, fundamentals: dict) -> list[dict]:
        opportunities = []
        for stock in watchlist_data:
            # Skip if error
            if "error" in stock:
                continue
                
            results = []
            stock_news = news_data.get(stock["symbol"], [])
            stock_fund = fundamentals.get(stock["symbol"], {})
            
            results.extend(self.scan_momentum_breakout(stock))
            results.extend(self.scan_bearish_breakdown(stock, stock_news))
            results.extend(self.scan_earnings_momentum(stock, stock_fund, stock_news))
            results.extend(self.scan_panic_selloff(stock, stock_news))
            results.extend(self.scan_mean_reversion(stock))
            
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

        if (price_vs_ema20 == "above" and
            price_vs_vwap == "above" and
            vol_ratio > 1.5 and
            55 < rsi < 80 and
            macd == "bullish"):

            reasons = [
                f"Price above 20 EMA ({stock['ema_20']})",
                f"Price above VWAP ({stock['vwap']})",
                f"Volume {vol_ratio}x average",
                f"RSI at {rsi} (bullish momentum)",
                f"MACD bullish crossover"
            ]

            boosters = 0
            if stock["price_vs_ema50"] == "above":
                boosters += 1
                reasons.append(f"Price above 50 EMA ({stock['ema_50']})")
            if vol_ratio > 2.5:
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
        if (stock["price_vs_ema20"] == "below" and
            stock["price_vs_vwap"] == "below" and
            stock["volume_ratio"] > 1.5 and
            stock["rsi"] < 45 and
            stock["macd"] == "bearish"):
            
            strength = "moderate"
            reasons = ["Price broke below 20 EMA and VWAP with volume"]
            
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
        if stock["bb_position"] == "oversold" and stock["rsi"] < 35 and stock["volume_ratio"] < 1.0:
            return [{
                "symbol": stock["symbol"],
                "signal_type": "bullish_mean_reversion",
                "signal_strength": "moderate",
                "suggested_action": "BUY",
                "suggested_position": "LONG",
                "reasons": ["Price over-extended to downside, volume drying up"],
                "indicators": stock
            }]
        elif stock["bb_position"] == "overbought" and stock["rsi"] > 70 and stock["volume_ratio"] < 1.0:
            return [{
                "symbol": stock["symbol"],
                "signal_type": "bearish_mean_reversion",
                "signal_strength": "moderate",
                "suggested_action": "SHORT",
                "suggested_position": "SHORT",
                "reasons": ["Price over-extended to upside, volume drying up"],
                "indicators": stock
            }]
        return []
