import QtQuick 2.6
QtObject {
    property real throttle: 0
    property real rudder: 0
    property real flaps: 0
    property real brake: 0
    property bool gearDown: false
    property real aileron: 0
    property real elevator: 0
    property bool tiltActive: false
    property bool cranking: false
    property bool engineOn: false
    function cycleView() {}
    function setFieldOfView(d) {}
    function setViewOffsets(h, p) {}
    function calibrate() {}
    function startEngine() {}
    function stopEngine() {}
    property var tutorials: []
    property bool tutorialRunning: false
    property string tutorialMessage: ""
    property string tutorialName: ""
    property bool paused: false
    function setPaused(p, hz) {}
    function refreshTutorials() {}
    function startTutorial(n) {}
    function stopTutorial() {}
    property bool reversing: false
    property real reverseDepth: 0
    function setReverseDepth(d) {}
    function setReverse(on) {}
    function startEngineWhenLoaded(t) {}
}
