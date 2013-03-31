var currentData = [];
var properties = [];

function displayData() {
    var i, j, checkedValue, props, oTable, data, row;

    checkedValue = $('input[name=display]').filter(':checked').val();
    $("#num-results").text("Number of results = " + currentData.length);
    if (checkedValue == "tree" && currentData.length > 0) {
        try {
            visualize(currentData);
            $("#result-tree").show();
            $("#num-results").show();
            $("#results-table-div").hide();
            $("#plot-div").hide();
        }
        catch (e) {
            alert("Sorry error in json string, please correct and try again: " + e.message);
        }
    }
    else if (checkedValue == "table" && currentData.length > 0) {
        props = [];
        for (j = 0; j < properties.length; j++) {
            props.push({ "sTitle": properties[j]});
        }
        $("#results-table-div").empty();
        $("#results-table-div").html("<table id='results-table'></table>");
        oTable = $('#results-table').dataTable(
            {
                "bPaginate": true,
                "bLengthChange": true,
                "bFilter": true,
                "bSort": true,
                "bInfo": true,
                "bAutoWidth": true,
                "sDom": 'T<"clear">lfrtip',
                "oTableTools": {
                    "sSwfPath": "/static/js/DataTables-1.9.4/extras/TableTools/media/swf/copy_csv_xls_pdf.swf",
                    "aButtons": [
                        "copy",
                        "print",
                        {
                            "sExtends":    "collection",
                            "sButtonText": "Export",
                            "aButtons":    [ "csv", "xls", "pdf" ]
                        }
                    ]
                },
                "sPaginationType": "full_numbers",
                "iDisplayLength": 50,
                "sScrollX": "100%",
                "sScrollY": "500px",
                "bScrollCollapse": true,
                "aoColumns": props
            });
        $("#num-results").text("Number of results = " + currentData.length);
        data = [];
        for (i = 0; i < currentData.length; i++) {
            row = [];
            for (j = 0; j < properties.length; j++) {
                row.push(JSON.stringify(currentData[i][properties[j]], null, "    "));
            }
            data.push(row);
        }
        oTable.fnClearTable();
        oTable.fnAddData(data);
        $("#results-table-div").show();
        $("#num-results").show();
        $("#result-tree").hide();
        $("#plot-div").hide();
    }
    else{
        data = [];
        var labels = [];
        for (i = 0; i < currentData.length; i++) {
            row = [];
            for (j = 0; j < properties.length; j++) {
                row.push(currentData[i][properties[j]]);
                labels.push(properties[j]);
            }
            data.push(row);
        }
        var chartData = [];
        chartData.push({
            name : "",
            color: 'blue',
            data: data
        });
        var xAxisOptions = {
            title : {
                text : labels[0],
                style: {
                    font: 'normal 1.5em Helvetica, sans-serif',
                    color: 'black'
                }
            },
            lineWidth:2,
            gridLineWidth:1,
            labels:{
                style: {
                    font: 'normal 1.2em Helvetica, sans-serif',
                    color: 'black'
                }
            }
        };
        var yAxisOptions = {
            title: {
                text: labels[1],
                style: {
                    font: 'normal 1.5em Helvetica, sans-serif',
                    color: 'black'
                }
            },
            lineWidth:1,
            gridLineWidth:1,
            labels:{
                style: {
                    font: 'normal 1.2em Helvetica, sans-serif',
                    color: 'black'
                }
            }

        };
        var chart = new Highcharts.Chart({
            chart: {
                renderTo: "plot-div",
                type: 'scatter',
                zoomType : 'xy',
                animation: false
            },
            credits: {
                enabled: false
            },
            title: {
                text: "Plot of " + labels[1] + " vs " + labels[0]
            },
            xAxis: xAxisOptions,
            yAxis: yAxisOptions,
            legend: {
                enabled: false
            },
            tooltip: {
                formatter: function() {
                    return this.point.x + ", " + this.point.y;
                },
                style : {
                    font: 'normal 1em Helvetica, sans-serif'
                }
            },
            series: chartData
        });
        $("#results-table-div").hide();
        $("#num-results").show();
        $("#result-tree").hide();
        $("#plot-div").show();

    }
}

function doQuery() {
    var crit, prop, opts, limit;
    crit = $("#criteria-input").val();
    prop = $("#properties-input").val();
    limit = $("#limit-slider").slider("value");
    opts = {
        img: '/static/images/spinner-large.gif',
        height: 50,
        width: 50
    };
    $("#search-button").spinner(opts);

    $.ajax({
               url: "/rest/query",
               type: "POST",
               data: {
                   criteria: crit,
                   properties: prop,
                   limit: limit
               }
           }
    ).success(function (data) {
                  $("#search-button").spinner('remove');
                  if (data["valid_response"]) {
                      currentData = data["results"];
                      properties = data["properties"];
                      displayData();
                  } else {
                      $("#error_msg").text(data["error"]);
                      $("#error_msg").show();
                  }
              })
        .error(function (data) {
                   $("#search-button").spinner('remove');
                   $("#error_msg").text(data["error"]);
                   $("#error_msg").show();
               });
}


var transforms = {
    'object': {'tag': 'div', 'class': 'package ${show} ${type}', 'children': [
        {'tag': 'div', 'class': 'header', 'children': [
            {'tag': 'div', 'class': function (obj) {
                if (getValue(obj.value) !== undefined) return('arrow hide');
                else return('arrow');
            }},
            {'tag': 'span', 'class': 'name', 'html': '${name}'},
            {'tag': 'span', 'class': 'value', 'html': function (obj) {
                var value = getValue(obj.value);
                if (value !== undefined) return(" : " + value);
                else return('');
            }},
            {'tag': 'span', 'class': 'type', 'html': '${type}'}
        ]},
        {'tag': 'div', 'class': 'children', 'children': function (obj) {
            return(children(obj.value));
        }}
    ]}
};

function visualize(json) {
    $('#result-tree').html('');
    $('#result-tree').json2html(convert('Results', json, 'open'), transforms.object);
    regEvents();
}

function getValue(obj) {
    var type = $.type(obj);

    //Determine if this object has children
    switch (type) {
        case 'array':
        case 'object':
            return(undefined);
            break;

        case 'function':
            //none
            return('function');
            break;

        case 'string':
            return("'" + obj + "'");
            break;

        default:
            return(obj);
            break;
    }
}

//Transform the children
function children(obj) {
    var type = $.type(obj);

    //Determine if this object has children
    switch (type) {
        case 'array':
        case 'object':
            return($.json2html(obj, transforms.object));
            break;

        default:
            //This must be a litteral
            break;
    }
}

function convert(name, obj, show) {

    var type = $.type(obj);

    if (show === undefined) show = 'closed';

    var children = [];

    //Determine the type of this object
    switch (type) {
        case 'array':
            //Transform array
            //Itterrate through the array and add it to the elements array
            var len = obj.length;
            for (var j = 0; j < len; ++j) {
                //Concat the return elements from this objects tranformation
                children[j] = convert(j, obj[j]);
            }
            break;

        case 'object':
            //Transform Object
            var j = 0;
            for (var prop in obj) {
                children[j] = convert(prop, obj[prop]);
                j++;
            }
            break;

        default:
            //This must be a litteral (or function)
            children = obj;
            break;
    }

    return( {'name': name, 'value': children, 'type': type, 'show': show} );

}

function regEvents() {

    $('.header').click(function () {
        var parent = $(this).parent();

        if (parent.hasClass('closed')) {
            parent.removeClass('closed');
            parent.addClass('open');
        } else {
            parent.removeClass('open');
            parent.addClass('closed');
        }
    });
}

window.onload = function () {
    $('input').addClass("ui-corner-all");
    $("input").keyup(function () {
        $("#error_msg").hide();
    });
    $(".buttons").button();

    $("#search-button").click(function () {
        doQuery();
    });

    $("input[name=display]").click(function () {
        displayData();
    });

    $("input[type=text]").keyup(function (e) {
        if (e.keyCode == 13) {
            doQuery();
        }
    });
//    $("#skip-slider").slider(
//        {
//            orientation: "vertical",
//            range: "min",
//            min: 0,
//            max: 1000,
//            value: 0,
//            slide: function(event, ui)
//            {
//                $("#skip-text").text("Skip: " + ui.value);
//            }
//        });
    $("#limit-slider").slider(
        {
            range: "min",
            min: 0,
            max: 100,
            value: 30,
            slide: function(event, ui)
            {
                $("#limit-text").text(ui.value);
            }
        });

}