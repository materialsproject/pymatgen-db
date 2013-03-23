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
    }
}

function doQuery(){
    var crit, prop, opts;
    crit = $("#criteria-input").val();
    prop = $("#properties-input").val();

    opts = {
        img: '/static/images/spinner-large.gif',
        height: 50,
        width: 50
    };
    $("#search-button").spinner(opts);

    $.ajax({
               url: "/query",
               type: "POST",
               data: {criteria: crit, properties: prop}
           }
    ).success(function (data) {
                  $("#search-button").spinner('remove');
                  if (data["valid_response"]) {
                      currentData = data["results"];
                      properties = data["properties"];
                      displayData();
                  } else {
                      $("#error_msg").text(data["error_msg"]);
                      $("#error_msg").show();
                  }
              })
        .error(function (data) {
                   $("#search-button").spinner('remove');
                   $("#error_msg").text(data["error_msg"]);
                   $("#error_msg").show();
               });
}

window.onload = function () {
    $('input').addClass("ui-corner-all");
    $("input").keyup(function(){
        $("#error_msg").hide();
    });
    $(".buttons").button();

    $("#search-button").click(function () {
        doQuery();
    });

    $("input[name=display]").click(function(){
        displayData();
    });

    $("input[type=text]").keyup(function(e) {
        if (e.keyCode==13)
        {
            doQuery();
        }
    });

}