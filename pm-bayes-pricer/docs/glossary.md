# Glossary

Plain-English meanings of the terms used in the code and notebooks.

**Basis point (bp).** One hundredth of a percentage point. A "25 bps cut" lowers the Fed's rate by 0.25 points.

**Bayes' rule.** The rule for updating a belief when evidence arrives: new belief is proportional to (how well the belief predicted the evidence) × (what you believed before).

**Bayes factor.** How many times better one prior or model predicted the data than another. Around 10 is usually called strong support.

**Bid / ask / mid.** The bid is the best price a buyer is offering; the ask is the best price a seller wants. The mid is halfway between and is our best guess of fair value.

**Brier score.** Average squared gap between forecast and outcome. Lower is better; always saying 50% scores 0.25.

**Calibration.** Whether "70%" forecasts come true about 70% of the time.

**Conjugate prior.** A starting belief whose updated version has the same mathematical shape, so updating is just arithmetic (add the counts).

**Contract.** A bet paying $1 if the event happens, $0 otherwise. Its price in dollars is the market's probability.

**Credible interval.** A range that contains the true probability with stated confidence (e.g. 90%), given the evidence so far.

**Dirichlet distribution.** A belief over several mutually exclusive outcomes, stored as pseudo-counts.

**Dutch book.** A set of trades that guarantees a profit whatever happens.

**Edge.** Your probability minus the price you pay, after fees.

**FOMC.** The Federal Open Market Committee, which sets US interest rates at about eight scheduled meetings a year.

**Isotonic regression.** The smallest adjustment that makes a sequence go only one way (here, only down). Used to repair inconsistent ladders.

**Kelly criterion.** The stake size that maximises long-run bankroll growth. Fractional Kelly bets a fixed fraction of it to reduce drawdowns.

**Ladder.** A series of "above X" contracts. Kalshi lists the Fed rate this way.

**Log loss.** Minus the log of the probability you gave to what actually happened. Punishes confident misses hard.

**Log-odds (logit).** ln(p / (1 - p)). On this scale, evidence adds up in a straight line.

**Longshot bias.** The habit of over-paying for unlikely outcomes, so longshots tend to be over-priced.

**Overround (vig).** How far the Yes prices of mutually exclusive outcomes add up above 100%; the venue's cushion.

**Proper scoring rule.** A score that is best, on average, when you report your true belief.

**Pseudo-counts.** A prior belief written as "as if I had already seen this many of each outcome".

**Resolution rules.** The precise wording that decides who wins. Two venues' "same" question can resolve differently.

**Taker fee.** A fee charged for taking a price that is already on the order book.

**Walk-forward backtest.** Testing a model by replaying history in time order, using only what was known at each point, so no future information leaks in.

**Barrier / touch contract.** A bet on whether the price *touches* a level at any moment in a window, not where it finishes. Also called a "one-touch".

**Basis (exchange basis).** The gap between the "same" price on two exchanges. For a barrier close to the price it can decide the contract, so the pricer uses the exchange that settles the contract.

**Brownian bridge.** The exact probability that a random path crossed a level *between* two observed points. Removes the bias of simulating at coarse steps.

**Filtered historical simulation (FHS).** Simulate the future by re-using real past shocks (divided by the volatility of the day) rescaled by a volatility model. Keeps real fat tails.

**HAR-RV.** A regression that forecasts volatility from yesterday's, last week's and last month's realised variance together.

**Implied volatility.** The volatility that makes a pricing formula reproduce a market price; a way to compare prices in one unit.

**Jensen's inequality.** Averaging a curved function over uncertainty gives a different answer from plugging in the average; it is why uncertainty about volatility changes barrier probabilities.

**Purged walk-forward.** Testing in time order, fitting only on data whose outcome was already known, so nothing from the future leaks in.

**QLIKE.** A loss for grading variance forecasts that is not dominated by a few explosive days.

**Realised variance.** The sum of squared short-interval returns; a direct measurement of how much the price moved.

**Reflection principle.** The mirror-image argument showing that, without drift, touching a level is twice as likely as finishing beyond it.

**Simulation-based calibration.** Checking that Bayesian update code is correct by simulating data from known truths and confirming the truths rank uniformly among the posterior draws.
