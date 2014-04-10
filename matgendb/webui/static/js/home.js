var currentData = [];
var properties = [];
var collection_keys = [];

function displayData() {
    var i, j, checkedValue, props, oTable, data, row;

    checkedValue = $('input[name=display]').filter(':checked').val();
    $("#num-results").text("Number of results = " + currentData.length);
    if (checkedValue == "tree" && currentData.length > 0) {
        try {
            visualize(currentData);
            $("#result-tree").show();
            $("#num-results").show();
            $("#result-plot").hide();
            $("#results-table-div").hide();
        }
        catch (e) {
            alert("Sorry error in json string, please correct and try again: " + e.message);
        }
    }
    else if (checkedValue == "plot" && currentData.length > 0) {
        try {
	    $("#result-plot").hide();
            visualize_plot(currentData);
            $("#result-plot").show();
            $("#num-results").show();
            $("#result-tree").hide();
            $("#results-table-div").hide();
        }
        catch (e) {
            alert("Sorry error in json string, please correct and try again: " + e.message);
        }
    }
    else if (currentData.length > 0) {
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
        $("#result-plot").hide();
    }
}

function doQuery() {
    var j, crit, prop, opts, limit;
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

		      // check if it makes sense to plot
                      $("#plot-option").hide();
		      $("#result-plot").hide();
                      if (typeof(currentData[0][properties[0]]) == 'number') {
                          for (j = 1; j < properties.length; j++) {
                              if (typeof(currentData[0][properties[j]]) == 'number') {
                                  // there's at least one property to plot against the first
                                  $("#plot-option").show();
				  break;
                              }
                          }
                      }

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

function visualize_plot(json) {
    
    alldata = [];
    
    for (j = 1; j < properties.length; j++) {
	values = [];
	for (i = 0; i < currentData.length; i++) {
            x = currentData[i][properties[0]];
            y = currentData[i][properties[j]];
            values.push([x,y]);
	}
	values.sort(function(a,b){return a[0]-b[0]});
	series = { label: properties[j], data: values };
	alldata.push(series);
    }
    
    var options = {
	series: {
            lines: { show: true },
            points: { show: true }
	}
    };
    
    try {
	$.plot($("#result-plot"), alldata, options);
    }
    catch (e) {
	alert("Sorry error in plot, please correct and try again: " + e.message);
    }
    
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

/**
 * Get/set collection keys, for completion.
 */
function getCollKeys() {
    return collection_keys;
}
function setCollKeys(k) {
    collection_keys = k;
}

window.onload = function () {
    $("#plot-option").hide();

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

    // from http://jqueryui.com/autocomplete/#multiple
    $(function() {
	// TODO: get tags from db schema (save them to a schema collection when inserted?) instead of hardcoded
	var availableTags = getCollKeys();

	function split( val ) {
	    return val.split( / \s*/ );
	}

	function extractLast( term ) {
	    return split( term ).pop();
	}

	$( "#properties-input" )
	// don't navigate away from the field on tab when selecting an item
	    .bind( "keydown", function( event ) {
		if ( event.keyCode === $.ui.keyCode.TAB &&
		     $( this ).data( "ui-autocomplete" ).menu.active ) {
		    event.preventDefault();
		}
	    })
	    .autocomplete({
		minLength: 0,

		source: function( request, response ) {
		    // delegate back to autocomplete, but extract the last term
		    response( $.ui.autocomplete.filter(
			availableTags, extractLast( request.term ) ) );
		},
		focus: function() {
		    // prevent value inserted on focus
		    return false;
		},
		select: function( event, ui ) {
		    var terms = split( this.value );
		    // remove the current input
		    terms.pop();
		    // add the selected item
		    terms.push( ui.item.value );
		    // add placeholder to get the comma-and-space at the end
		    terms.push( "" );
		    this.value = terms.join( " " );
		    return false;
		}
	    });
    });
}
