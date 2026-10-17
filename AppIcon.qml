import QtQuick

// A bad desktop-entry path or invalid SVG must never leave a blank Dock cell.
Image {
    id: root
    property url requestedSource
    property url fallbackSource: Qt.resolvedUrl("assets/icons/application.svg")
    property bool failed: false
    source: failed || requestedSource.toString() === "" ? fallbackSource : requestedSource
    onRequestedSourceChanged: failed = false
    onStatusChanged: if (status === Image.Error && !failed) failed = true
    smooth: true
    mipmap: true
}
