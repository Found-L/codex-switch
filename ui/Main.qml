import QtQuick
import QtQuick.Window
import QtQuick.Controls

Window {
    id: root
    objectName: "mainWindow"
    width: bridge.compact ? 372 : 452
    height: bridge.compact ? 302 : 616
    visible: false
    color: "transparent"
    title: "Codex Switch"
    flags: Qt.Window | Qt.FramelessWindowHint
    property string page: bridge.state.api_ready ? "connections" : "key"
    property string displayedPage: ""
    property bool sceneReady: false
    property bool showKey: false
    readonly property color accent: "#6055da"
    readonly property color ink: "#252938"
    readonly property color muted: "#858998"
    readonly property bool api: bridge.state.mode === "api"
    function t(zh, en) { return bridge.language === "zh" ? zh : en }
    Shortcut { sequence: bridge.isMac ? "Meta+M" : "Ctrl+M"; onActivated: bridge.hideToTray() }
    Shortcut { sequence: bridge.isMac ? "Meta+Shift+M" : "Ctrl+Shift+M"; onActivated: bridge.toggleCompact() }
    Shortcut { sequence: bridge.isMac ? "Meta+Q" : "Ctrl+Q"; onActivated: bridge.quitApp() }

    onClosing: function(event) {
        if (!bridge.testingMode) { event.accepted = false; bridge.hideToTray() }
    }
    onVisibilityChanged: function(newVisibility) {
        if (newVisibility === Window.Minimized && !bridge.testingMode) bridge.hideToTray()
        if (visible) appear.restart()
    }
    Component.onCompleted: { displayedPage = page; sceneReady = true }
    onPageChanged: {
        if (page !== "key") { keyField.clear(); showKey = false }
        if (sceneReady && visible) pageTransition.restart()
        else displayedPage = page
    }
    SequentialAnimation {
        id: pageTransition
        NumberAnimation { target: pages; property: "opacity"; to: 0; duration: 70; easing.type: Easing.OutQuad }
        ScriptAction { script: root.displayedPage = root.page }
        NumberAnimation { target: pages; property: "opacity"; to: 1; duration: 110; easing.type: Easing.OutCubic }
    }

    Connections {
        target: bridge
        function onOpenPage(name) { root.page = name }
        function onKeySaved() { keyField.clear(); root.showKey = false }
        function onWindowHidden() { keyField.clear(); root.showKey = false }
    }

    component SoftButton: Rectangle {
        id: control
        property string text: ""
        property bool primary: false
        property bool refreshIcon: false
        signal clicked()
        Accessible.role: Accessible.Button
        Accessible.name: refreshIcon ? root.t("刷新状态", "Refresh status") : text
        Accessible.onPressAction: clicked()
        activeFocusOnTab: true
        Keys.onReturnPressed: clicked()
        Keys.onSpacePressed: clicked()
        height: 44
        radius: 12
        color: primary ? (hit.containsMouse ? "#7166e4" : root.accent) : (hit.containsMouse ? "#e9eaf2" : "#eff0f6")
        opacity: enabled ? 1 : 0.5
        Behavior on color { ColorAnimation { duration: 130 } }
        Behavior on opacity { NumberAnimation { duration: 120 } }
        Text { anchors.centerIn: parent; text: control.text; color: control.primary ? "white" : root.ink; font.family: bridge.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold }
        Canvas {
            visible: control.refreshIcon
            anchors.centerIn: parent; width: 18; height: 18
            onPaint: {
                const c = getContext("2d"); c.clearRect(0,0,18,18);
                c.strokeStyle = "#737787"; c.lineWidth = 1.5; c.lineCap = "round";
                c.beginPath(); c.arc(9,9,5.5,0.2,5.5); c.stroke();
                c.beginPath(); c.moveTo(13,3); c.lineTo(13.4,6.3); c.lineTo(10.1,6.1); c.stroke();
            }
        }
        MouseArea { id: hit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: control.clicked() }
    }

    component GlyphButton: Rectangle {
        id: glyphControl
        property string kind: "close"
        property string tip: ""
        signal clicked()
        Accessible.role: Accessible.Button
        Accessible.name: tip
        Accessible.onPressAction: clicked()
        width: 28; height: 28; radius: 9
        color: glyphHit.containsMouse ? (kind === "close" ? "#f7e7e9" : "#e7e9f1") : "transparent"
        Behavior on color { ColorAnimation { duration: 130 } }
        ToolTip.visible: glyphHit.containsMouse
        ToolTip.text: tip
        ToolTip.delay: 600
        Canvas {
            anchors.centerIn: parent; width: 16; height: 16
            onPaint: {
                const c = getContext("2d"); c.clearRect(0,0,16,16); c.strokeStyle = "#737787"; c.lineWidth = 1.5; c.lineCap = "round";
                c.beginPath();
                if (glyphControl.kind === "close") { c.moveTo(4,4); c.lineTo(12,12); c.moveTo(12,4); c.lineTo(4,12) }
                else { c.rect(2.5,3.5,11,9); c.moveTo(9,7); c.lineTo(13,7); c.moveTo(9,7); c.lineTo(9,12) }
                c.stroke()
            }
        }
        MouseArea { id: glyphHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: glyphControl.clicked() }
    }

    component ConnectionPicker: Rectangle {
        id: picker
        property bool mini: false
        height: mini ? 72 : 98
        radius: 18
        color: "#e9ebf2"
        Rectangle {
            id: pill
            objectName: picker.mini ? "miniSelectionPill" : "selectionPill"
            x: root.api ? 4 + (picker.width - 8) / 2 : 4; y: 4
            width: (picker.width - 8) / 2; height: parent.height - 8
            radius: 14
            color: "white"
            border.color: "#e3e5ed"
            Behavior on x { NumberAnimation { duration: 210; easing.type: Easing.OutCubic } }
        }
        Repeater {
            model: ["account", "api"]
            Item {
                id: choice
                required property string modelData
                required property int index
                readonly property bool selected: (modelData === "api") === root.api
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData === "api" ? (bridge.state.api_label || "API") : root.t("Codex 账号", "Codex account")
                Accessible.checked: selected
                Accessible.onPressAction: bridge.switchTo(modelData)
                x: 4 + index * (picker.width - 8) / 2; y: 4
                width: (picker.width - 8) / 2; height: picker.height - 8
                Text {
                    x: 14; y: picker.mini ? 11 : 16
                    text: choice.modelData === "api" ? "API" : "C"
                    color: choice.selected ? root.accent : "#989dab"
                    font.family: bridge.fontFamily; font.pixelSize: picker.mini ? 11 : 12; font.weight: Font.Bold
                }
                Text {
                    x: 14; y: picker.mini ? 32 : 42
                    text: choice.modelData === "api" ? (bridge.state.api_label || "API") : root.t("Codex 账号", "Codex account")
                    color: choice.selected ? root.ink : "#7d8292"
                    font.family: bridge.fontFamily; font.pixelSize: picker.mini ? 12 : 14; font.weight: Font.DemiBold
                }
                Text {
                    visible: !picker.mini
                    x: 14; y: 65
                    text: choice.modelData === "api" ? root.t("按量计费", "Pay as you go") : root.t("账号额度", "Account credits")
                    color: "#9599a6"; font.family: bridge.fontFamily; font.pixelSize: 10
                }
                Canvas {
                    anchors.right: parent.right; anchors.rightMargin: 14; y: picker.mini ? 13 : 18
                    width: 13; height: 13; opacity: choice.selected ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                    onPaint: {
                        const c = getContext("2d"); c.clearRect(0,0,13,13);
                        c.strokeStyle = root.accent; c.lineWidth = 1.7; c.lineCap = "round";
                        c.beginPath(); c.moveTo(2,6.5); c.lineTo(5,9.5); c.lineTo(11,3.5); c.stroke();
                    }
                }
                MouseArea { anchors.fill: parent; enabled: !bridge.busy; cursorShape: Qt.PointingHandCursor; onClicked: bridge.switchTo(choice.modelData) }
            }
        }
    }

    Repeater {
        model: 7
        Rectangle {
            required property int index
            x: 12 - index; y: 16 - index
            width: root.width - 24 + index * 2; height: root.height - 28 + index * 2
            radius: 24 + index
            color: "#111a35"; opacity: 0.014
        }
    }
    Rectangle {
        id: panel
        anchors.fill: parent; anchors.margins: 12
        radius: 24
        color: "#f7f8fc"
        border.width: 1; border.color: "#ffffff"
        clip: true
        transformOrigin: Item.Center
        opacity: 0
        scale: 0.98
        ParallelAnimation {
            id: appear
            NumberAnimation { target: panel; property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { target: panel; property: "scale"; from: 0.98; to: 1; duration: 190; easing.type: Easing.OutCubic }
        }
        MouseArea { x: 0; y: 0; width: parent.width; height: 76; onPressed: root.startSystemMove() }
        Image { x: 22; y: 20; width: 34; height: 34; source: bridge.logoUrl; smooth: true; mipmap: true }
        Text { x: 66; y: 20; text: "Codex Switch"; color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 16; font.weight: Font.DemiBold }
        Text { x: 66; y: 42; text: root.t("连接，随你切换", "Your connection, simply."); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 19; y: 21; spacing: 3
            GlyphButton { kind: "mini"; tip: bridge.compact ? root.t("展开面板", "Full panel") : root.t("迷你窗口", "Mini window"); onClicked: bridge.toggleCompact() }
            GlyphButton { kind: "close"; tip: bridge.isMac ? root.t("收进菜单栏", "Hide to menu bar") : root.t("收进托盘", "Hide to tray"); onClicked: bridge.hideToTray() }
        }

        Rectangle {
            id: tabs
            visible: !bridge.compact
            x: 24; y: 84; width: parent.width - 48; height: 38; radius: 12; color: "#edeef5"
            Rectangle {
                x: 3 + (root.page === "connections" ? 0 : root.page === "key" ? 1 : root.page === "models" ? 2 : 3) * (tabs.width - 6) / 4
                y: 3; width: (tabs.width - 6) / 4; height: 32; radius: 9; color: "white"; border.color: "#e2e4ec"
                Behavior on x { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
            }
            Repeater {
                model: [{key:"connections",zh:"连接",en:"Connection"},{key:"key",zh:"API 配置",en:"API setup"},{key:"models",zh:"模型",en:"Models"},{key:"terminal",zh:"终端",en:"Terminal"}]
                Item {
                    required property var modelData; required property int index
                    x: 3 + index * (tabs.width - 6) / 4; width: (tabs.width - 6) / 4; height: 38
                    Text { anchors.centerIn: parent; text: root.t(modelData.zh,modelData.en); color: root.page === modelData.key ? root.ink : "#8a8e9d"; font.family: bridge.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.page = modelData.key }
                }
            }
        }

        Item {
            id: pages
            objectName: "pagesArea"
            visible: !bridge.compact
            enabled: !pageTransition.running
            x: 24; y: 144; width: parent.width - 48; height: parent.height - 240
            Item {
                id: connectionsPage
                objectName: "connectionsPage"
                anchors.fill: parent
                visible: root.displayedPage === "connections"
                Rectangle {
                    width: parent.width; height: 104; radius: 18; color: "white"; border.color: "#e4e6ef"
                    Text { x: 20; y: 18; text: root.t("当前连接配置", "CURRENT CONFIGURATION"); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 10; font.letterSpacing: 0.4 }
                    Text { x: 20; y: 43; text: root.api ? (bridge.state.api_label || "API") : bridge.state.mode === "other" ? root.t("其他提供商", "Other provider") : root.t("Codex 账号", "Codex account"); color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 26; font.weight: Font.DemiBold }
                    Text { x: 20; y: 80; width: parent.width - 40; elide: Text.ElideRight; text: root.t("配置模型：", "Configured model: ") + (bridge.state.model || root.t("Codex 默认", "Codex default")); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
                }
                ConnectionPicker { y: 116; width: parent.width }
                SoftButton { x: 0; y: 226; width: parent.width - 52; height: 36; text: root.t("管理 API Key", "Manage API key"); onClicked: root.page = "key" }
                SoftButton { x: parent.width - 42; y: 226; width: 42; height: 36; refreshIcon: true; enabled: !bridge.busy; onClicked: bridge.refresh() }
                Rectangle {
                    objectName: "runtimeSummary"; y: 274; width: parent.width; height: 78; radius: 13; color: "white"; border.color: "#e4e6ef"
                    Text { x: 12; y: 10; text: root.t("会话运行状态 · 独立于配置", "Chat runtime · separate from config"); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
                    Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 10; text: bridge.busy ? root.t("处理中", "Working") : root.t("只读检查", "Check"); color: root.accent; font.family: bridge.fontFamily; font.pixelSize: 11; MouseArea { anchors.fill: parent; enabled: !bridge.busy; onClicked: bridge.inspectRuntime() } }
                    Text { x: 12; y: 32; width: parent.width - 24; wrapMode: Text.WordWrap; text: bridge.runtimeState.status === "connected" ? root.t("已读到本机进程目录，当前会话模型与计费仍未知。", "Local server catalog read. Current chat model and billing remain unknown.") : root.t("未接入桌面；当前会话模型与计费连接未知。", "Desktop is not connected. Current model and billing route are unknown."); color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 10 }
                    Text { x: 12; y: 61; width: parent.width - 24; elide: Text.ElideRight; text: bridge.runtimeState.checked_at || root.t("检查不启动模型、不修改会话", "Check starts no model turn and changes no chat"); color: root.muted; font.pixelSize: 9 }
                }
            }

            Item {
                id: keyPage
                objectName: "keyPage"
                anchors.fill: parent
                visible: root.displayedPage === "key"
                Text { text: root.t("连接你的 API", "Connect your API"); color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 21; font.weight: Font.DemiBold }
                Text { y: 37; width: parent.width; text: root.t("支持 OpenAI、DeepSeek 和 New API 网关。", "OpenAI, DeepSeek and New API gateways."); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 12; wrapMode: Text.WordWrap }
                Text { y: 68; text: "Base URL"; color: "#656b7b"; font.family: bridge.fontFamily; font.pixelSize: 11 }
                TextField {
                    id: urlField
                    objectName: "baseUrlField"
                    y: 88; width: parent.width; height: 40; leftPadding: 12
                    text: bridge.state.base_url || "https://api.openai.com/v1"
                    placeholderText: "https://your-gateway/v1"
                    enabled: !bridge.busy; selectByMouse: true
                    font.family: bridge.fontFamily; font.pixelSize: 11; color: root.ink
                    background: Rectangle { radius: 10; color: "white"; border.color: urlField.activeFocus ? root.accent : "#dfe3ee" }
                }
                Text { y: 145; text: "API Key"; color: "#656b7b"; font.family: bridge.fontFamily; font.pixelSize: 11; font.weight: Font.DemiBold }
                TextField {
                    id: keyField
                    objectName: "apiKeyField"
                    x: 0; y: 165; width: parent.width; height: 44
                    leftPadding: 14; rightPadding: 62
                    font.family: bridge.fontFamily; font.pixelSize: 13
                    color: root.ink; placeholderText: bridge.state.key_saved ? root.t("已保存，留空保留原 Key", "Saved. Leave blank to keep it.") : "sk-…"
                    echoMode: root.showKey ? TextInput.Normal : TextInput.Password
                    enabled: !bridge.busy
                    background: Rectangle { radius: 12; color: "white"; border.color: keyField.activeFocus ? root.accent : "#dfe3ee"; Behavior on border.color { ColorAnimation { duration: 150 } } }
                    onAccepted: bridge.saveConnection(text, urlField.text)
                }
                Text {
                    x: parent.width - 54; y: 180; width: 48; horizontalAlignment: Text.AlignHCenter
                    text: root.showKey ? root.t("隐藏", "Hide") : root.t("显示", "Show")
                    color: root.accent; font.family: bridge.fontFamily; font.pixelSize: 10
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showKey = !root.showKey }
                }
                Text { y: 223; width: parent.width; text: bridge.isMac ? root.t("Key 保存在当前用户的 macOS 钥匙串中。", "Stored in your macOS login Keychain.") : root.t("Key 保存在当前 Windows 用户的凭据管理器中。", "Stored in Windows Credential Manager for your user."); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 11; wrapMode: Text.WordWrap }
                SoftButton { y: 267; width: parent.width; primary: true; text: bridge.busy ? root.t("正在保存…", "Saving…") : root.t("保存 API 配置", "Save API connection"); enabled: !bridge.busy; onClicked: bridge.saveConnection(keyField.text, urlField.text) }
                Text { y: 328; text: root.t("创建 OpenAI API Key ↗", "Create an OpenAI API key ↗"); color: root.accent; font.family: bridge.fontFamily; font.pixelSize: 11; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.openLink("key") } }
                Text { visible: false; y: 355; text: root.t("还没有 Codex？查看安装说明 ↗", "Need Codex? Open the installation guide ↗"); color: "#9a9fac"; font.family: bridge.fontFamily; font.pixelSize: 10; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.openLink("codex") } }
            }

            ModelsPage {
                id: modelsPage
                objectName: "modelsPage"
                host: root
                anchors.fill: parent
                visible: root.displayedPage === "models"
            }

            Item {
                id: terminalPage
                objectName: "terminalPage"
                anchors.fill: parent
                visible: root.displayedPage === "terminal"
                Text { text: root.t("终端里，也很顺手", "Just as easy in your terminal"); color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
                Text { y: 36; width: parent.width; text: bridge.isMac ? root.t("点击下方安装命令，再打开新终端。", "Install the command below, then open a new terminal.") : root.t("安装后重新打开终端，即可使用。", "Open a new terminal after installation."); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 11; wrapMode: Text.WordWrap }
                Column {
                    y: 82; width: parent.width; spacing: bridge.isMac ? 9 : 13
                    Repeater {
                        model: ["codex-switch setup --use", "codex-switch status", "codex-switch use api", "codex-switch use account"]
                        Rectangle {
                            required property string modelData
                            width: parent.width; height: bridge.isMac ? 46 : 53; radius: 12; color: "white"; border.color: "#e2e5ef"
                            Text { x: 13; anchors.verticalCenter: parent.verticalCenter; text: modelData; color: "#62677d"; font.family: bridge.isMac ? "Menlo" : "Consolas"; font.pixelSize: 11 }
                            Text { anchors.right: parent.right; anchors.rightMargin: 13; anchors.verticalCenter: parent.verticalCenter; text: root.t("复制", "Copy"); color: root.accent; font.family: bridge.fontFamily; font.pixelSize: 10; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.copyText(modelData) } }
                        }
                    }
                }
                SoftButton { visible: bridge.isMac; y: 312; width: parent.width; height: 40; text: root.t("安装 / 修复终端命令", "Install / repair terminal command"); enabled: !bridge.busy; onClicked: bridge.installCli() }
            }
        }

        Item {
            id: miniView
            objectName: "miniView"
            visible: bridge.compact
            x: 20; y: 76; width: parent.width - 40; height: parent.height - 88
            Text { text: root.t("当前连接配置", "CURRENT CONFIGURATION"); color: root.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { y: 21; text: root.api ? (bridge.state.api_label || "API") : bridge.state.mode === "other" ? root.t("其他提供商", "Other provider") : root.t("Codex 账号", "Codex account"); color: root.ink; font.family: bridge.fontFamily; font.pixelSize: 22; font.weight: Font.DemiBold }
            ConnectionPicker { y: 65; width: parent.width; mini: true }
            Text { y: 146; width: parent.width; text: bridge.busy ? root.t("正在保存…", "Saving…") : bridge.notice; color: bridge.isError ? "#bd5363" : "#4c9379"; font.family: bridge.fontFamily; font.pixelSize: 9; elide: Text.ElideRight }
            Text { y: 170; text: root.t("展开完整面板 ↗", "Open the full panel ↗"); color: root.accent; font.family: bridge.fontFamily; font.pixelSize: 10; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.toggleCompact() } }
            Text { y: 170; anchors.right: parent.right; text: "v" + bridge.version; color: "#a2a6b1"; font.family: bridge.fontFamily; font.pixelSize: 9 }
        }

        Text {
            objectName: "noticeText"
            x: 24; width: parent.width - 48; anchors.bottom: parent.bottom; anchors.bottomMargin: bridge.compact ? 37 : 47
            height: bridge.compact ? 20 : 34
            text: bridge.notice
            visible: !bridge.compact && opacity > 0
            opacity: bridge.notice.length ? 1 : 0
            color: bridge.isError ? "#bd5363" : "#4c9379"
            font.family: bridge.fontFamily; font.pixelSize: 11
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            Behavior on opacity { NumberAnimation { duration: 150 } }
        }
        Text { visible: !bridge.compact; x: 24; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; text: root.t("配置不代表已有会话；目录保存后需完全退出并重启 Codex。", "Config is not a running chat. Quit and restart Codex to load catalogs."); color: "#a2a6b1"; font.family: bridge.fontFamily; font.pixelSize: 9 }
        Text { visible: !bridge.compact; anchors.right: parent.right; anchors.rightMargin: 24; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; text: bridge.language === "zh" ? "EN" : "中"; color: "#8c90a0"; font.family: bridge.fontFamily; font.pixelSize: 10; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.toggleLanguage() } }
    }
}
