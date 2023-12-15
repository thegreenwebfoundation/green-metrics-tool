
var display_in_watts = localStorage.getItem('display_in_watts');
if(display_in_watts == 'true') display_in_watts = true;
else display_in_watts = false;

var display_in_metric_units = localStorage.getItem('display_in_metric_units');
if(display_in_metric_units == 'true') display_in_metric_units = true;
else display_in_metric_units = false;

var fetch_time_series = localStorage.getItem('fetch_time_series');
if(fetch_time_series == 'true') fetch_time_series = true;
else fetch_time_series = false;

let toggleWatts = () => {
    localStorage.setItem('display_in_watts', !display_in_watts);
    window.location.reload();
}

let toggleUnits = () => {
    localStorage.setItem('display_in_metric_units', !display_in_metric_units);
    window.location.reload();
}

let toggleTimeSeries = () => {
    localStorage.setItem('fetch_time_series', !fetch_time_series);
    window.location.reload();
}


(() => {

    $(window).on('load', function() {
      $('.ui.secondary.menu .item').tab();

      if(display_in_watts) $("#energy-display").text("Currently showing Watts");
      else $("#energy-display").text("Currently showing Joules");

      if(display_in_metric_units) $("#units-display").text("Currently showing metric units");
      else $("#units-display").text("Currently showing imperial units");

      if(fetch_time_series) $("#fetch-time-series-display").text("Currently fetching time series by default");
      else $("#fetch-time-series-display").text("Currently not fetching time series by default");


    });

})();
