// lightweight-charts always renders its time-axis labels using UTC internally, regardless
// of the viewer's browser timezone. NSE trading hours are fixed to IST, so every chart
// consumer must shift timestamps forward by IST's UTC offset before handing them to the
// chart — otherwise every viewer (whatever timezone their device is in) sees candle times
// that are ~5.5h behind the real IST wall-clock time the market actually traded at.
const IST_OFFSET_SECONDS = 5.5 * 60 * 60; // 19800

// Converts a datetime string/number (as returned by the backend, or a JS ms timestamp)
// into the epoch-seconds value lightweight-charts should be given so its UTC rendering
// displays the correct IST wall-clock time.
export const toChartTime = (dateInput) => {
    const ms = typeof dateInput === 'number' ? dateInput : new Date(dateInput).getTime();
    return Math.floor(ms / 1000) + IST_OFFSET_SECONDS;
};

// Same shift, for a live "now" tick that has no server-provided datetime.
export const nowChartTime = () => Math.floor(Date.now() / 1000) + IST_OFFSET_SECONDS;
