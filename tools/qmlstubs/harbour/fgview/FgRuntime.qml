import QtQuick 2.6
// Stub of the C++ type, for checking QML with qmlscene only.  Same members,
// no behaviour - enough for the engine to resolve every binding in the page.
QtObject {
    property bool dataReady: true
    property bool busy: false
    property bool simRunning: false
    property int progress: 0
    property string status: ""
    property string speed: ""
    property string simLog: ""
    function downloadData() {}
    function startSim(a, b, c, d, e, f) {}
    function stopSim() {}
    function fgRoot() { return "" }
    property var aircraft: []
    property var catalog: []
    property bool catalogBusy: false
    property string hangarStatus: ""
    property int hangarProgress: -1
    function refreshAircraft() {}
    function fetchCatalog() {}
    function installAircraft(id, dir, url) {}
    function removeAircraft(dir) {}
}
