$(document).ready(function () {
    (async () => {
        $('#jobs-table').DataTable({
            ajax: `${API_URL}/v1/jobs`,
            columns: [
                { data: 0, title: 'ID'},
                { data: 2, title: 'Name', render: (name, type, row) => row[1] == null ? name : `<a href="/stats.html?id=${row[1]}">${name}</a>`  },
                { data: 3, title: 'Url'},
                { data: 4, title: 'Filename'},
                { data: 5, title: 'Branch'},
                { data: 6, title: 'Machine'},
                { data: 7, title: 'State'},
                { data: 8, title: 'Last Update', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 9, title: 'Created at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            ],
            deferRender: true,
            order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });
        $('#machines-table').DataTable({
            ajax: `${API_URL}/v1/machines`,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name'},
                { data: 2, title: 'Available'},
                { data: 3, title: 'Status'},
                { data: 4, title: 'Status date', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 5, title: 'Cooldown after Job', render: function(el) {
                    return (el == null) ? 'awaiting info': `${Math.round(el/60)} Minutes`;
                }},
                { data: 6, title: 'Waiting Jobs'},
                { data: 7, title: 'Estimated waiting time', render: function(el, type, row) {

                    return (row[5] == null || row[7] == null) ? 'awaiting info' : `${Math.round(( (row[7]+row[5]) * row[6]) / 60)} Minutes`
                }},
            ],
            deferRender: true,
            //order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });


    })();
});
