import QtQuick
import QtQuick.Controls

Item {
    id: picker
    property var host
    property var selectedIds: []
    property string defaultId: ""
    property string scope: "candidate"
    property string connectionId: ""
    property bool draftDirty: false
    property string detailId: ""
    property var entries: bridge.state.models || []
    property var detail: entries.find(function(m) { return m.id === detailId }) || null
    function t(zh, en) { return host.t(zh, en) }
    function sourceLabel(m) {
        return m.category === "excluded" ? t("非编程模型", "Not for coding") : m.capability_source === "official" ? t("远端参数 · 未实测", "Remote metadata · untested") : m.capability_source === "bundled" ? t("Codex 内置参数 · API 未验证", "Codex defaults · API untested") : m.capability_source === "manual" ? t("手动参数 · 未实测", "Manual metadata · untested") : t("基础模板 · 未验证", "Basic template · unverified")
    }
    function reconcile(force) {
        const id = bridge.state.api_provider + "|" + bridge.state.base_url
        if (force || id !== connectionId || !draftDirty) {
            selectedIds = entries.filter(m => m.enabled && m.category !== "excluded").map(m => m.id)
            const savedDefault = bridge.state.api_model || bridge.state.model
            defaultId = selectedIds.indexOf(savedDefault) >= 0 ? savedDefault : (selectedIds[0] || "")
            draftDirty = false
        } else {
            selectedIds = selectedIds.filter(id => entries.some(m => m.id === id && m.category !== "excluded"))
            if (selectedIds.indexOf(defaultId) < 0) defaultId = selectedIds[0] || ""
        }
        connectionId = id
    }
    function toggle(id) {
        const m = entries.find(m => m.id === id)
        if (!m || m.category === "excluded" || bridge.busy) return
        selectedIds = selectedIds.indexOf(id) >= 0 ? selectedIds.filter(v => v !== id) : selectedIds.concat([id])
        if (selectedIds.indexOf(defaultId) < 0) defaultId = selectedIds[0] || ""
        draftDirty = true
    }
    function filtered() {
        const query = search.text.toLowerCase().trim()
        return entries.filter(m => (!query || m.id.toLowerCase().indexOf(query) >= 0)
            && (scope === "all" || (scope === "selected" ? selectedIds.indexOf(m.id) >= 0 : m.category === "candidate")))
            .sort((a,b) => (a.capability_source === "official" ? -1 : 0) - (b.capability_source === "official" ? -1 : 0) || a.id.localeCompare(b.id))
    }
    function loadDetails() {
        contextInput.text = detail ? String(detail.context_window) : "32768"
        reasoningInput.text = detail ? detail.reasoning.join(",") : ""
        imageInput.checked = detail ? detail.images : false
    }
    function openDetails(id) { detailId = id; loadDetails(); advanced.visible = true }
    function includeConfigured() {
        const id = bridge.state.model
        if (!entries.some(m => m.id === id && m.category !== "excluded")) return
        if (selectedIds.indexOf(id) < 0) selectedIds = selectedIds.concat([id])
        defaultId = id; draftDirty = true; search.text = ""; scope = "selected"
    }
    Component.onCompleted: reconcile(true)
    Connections {
        target: bridge
        function onStateChanged() { picker.reconcile(false) }
        function onCatalogApplied() { picker.reconcile(true) }
        function onCapabilitiesSaved() { if (advanced.visible) picker.loadDetails() }
    }

    Text { text: t("选择编程模型", "Choose coding models"); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
    Text { anchors.right: parent.right; y: 7; text: t("状态对照", "Compare states"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 11; MouseArea { anchors.fill: parent; onClicked: statePanel.visible = true } }
    Text {
        objectName: "catalogLoadNotice"
        y: 26; width: parent.width; height: 29; wrapMode: Text.WordWrap
        text: bridge.state.catalog_model_mismatch
            ? t("配置模型未在保存目录中；不代表当前会话异常。点「状态对照」查看。", "Configured model is outside the saved catalog. This does not diagnose a running chat. See Compare states.")
            : bridge.state.catalog_configured ? t("保存目录 ", "Saved catalog: ") + (bridge.state.saved_model_ids || []).length + t(" 个；桌面是否加载请单独检查。", " models. Desktop loading requires a separate check.")
            : t("勾选用于替换模型目录，不代表当前桌面菜单或调用权限。", "Selection replaces the catalog; it does not mirror the live menu or prove API access.")
        color: bridge.state.catalog_model_mismatch ? "#a26016" : host.muted; font.family: bridge.fontFamily; font.pixelSize: 10
    }
    TextField {
        id: search; objectName: "modelSearch"
        y: 59; width: parent.width - 92; height: 34; leftPadding: 11
        placeholderText: t("搜索模型名称…", "Search model names…"); selectByMouse: true
        font.family: bridge.fontFamily; font.pixelSize: 11; color: host.ink
        background: Rectangle { radius: 10; color: "white"; border.color: search.activeFocus ? host.accent : "#dfe3ee" }
    }
    Button {
        x: parent.width - 82; y: 59; width: 82; height: 34
        text: bridge.busy ? t("处理中", "Working") : !bridge.state.api_ready ? t("配置 API", "API setup") : t("同步", "Refresh")
        enabled: !bridge.busy; onClicked: bridge.syncModels()
        contentItem: Text { text: parent.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 11; font.weight: Font.DemiBold }
        background: Rectangle { radius: 10; color: parent.down ? "#e2dff9" : "#eceafa" }
    }
    Row {
        y: 103; spacing: 6
        Repeater {
            model: [{id:"candidate",zh:"编程候选",en:"Candidates"},{id:"selected",zh:"草稿所选",en:"Draft"},{id:"all",zh:"全部",en:"All"}]
            delegate: Rectangle {
                required property var modelData
                width: 76; height: 25; radius: 8; color: picker.scope === modelData.id ? "#e8e5fb" : "transparent"
                Text { anchors.centerIn: parent; text: picker.t(modelData.zh,modelData.en); color: picker.scope === modelData.id ? host.accent : host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
                MouseArea { anchors.fill: parent; onClicked: picker.scope = modelData.id }
            }
        }
    }
    Text { y: 109; anchors.right: parent.right; text: modelList.count + (picker.scope === "selected" ? t(" / 草稿 ", " / draft ") + picker.selectedIds.length : t(" / 名单 ", " / listed ") + entries.length); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 9 }
    Rectangle {
        x: 0; y: 138; width: parent.width; height: parent.height - y - 62
        color: "white"; radius: 13; border.color: "#e2e5ef"; clip: true
        ListView {
            id: modelList; objectName: "gatewayModelList"
            anchors.fill: parent; anchors.margins: 5
            model: picker.filtered(); clip: true; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                id: row
                required property var modelData
                width: modelList.width; height: 54; radius: 9
                readonly property bool selected: picker.selectedIds.indexOf(modelData.id) >= 0
                color: selected ? "#f0edfc" : "white"
                Behavior on color { ColorAnimation { duration: 100 } }
                CheckBox {
                    id: check; x: 5; anchors.verticalCenter: parent.verticalCenter; width: 26; height: 32
                    checked: row.selected; enabled: !bridge.busy && row.modelData.category !== "excluded"
                    Accessible.name: row.modelData.id
                    onClicked: picker.toggle(row.modelData.id)
                    indicator: Rectangle { width: 18; height: 18; radius: 6; anchors.centerIn: parent; color: check.checked ? host.accent : "white"; border.color: check.checked ? host.accent : "#ccd2e1"; Canvas { anchors.centerIn: parent; width: 12; height: 12; visible: check.checked; onPaint: { const c=getContext("2d"); c.strokeStyle="white"; c.lineWidth=1.5; c.lineCap="round"; c.beginPath(); c.moveTo(2,6); c.lineTo(5,9); c.lineTo(10,3); c.stroke() } } }
                }
                Text {
                    x: 38; y: 10; width: parent.width - 132; text: row.modelData.id; elide: Text.ElideRight
                    color: row.modelData.category === "excluded" ? "#a4a7b2" : host.ink
                    font.family: bridge.fontFamily; font.pixelSize: 11; font.weight: Font.DemiBold
                    ToolTip.visible: titleHit.containsMouse; ToolTip.text: row.modelData.id
                    MouseArea { id: titleHit; anchors.fill: parent; hoverEnabled: true; onClicked: picker.toggle(row.modelData.id) }
                }
                Text { x: 38; y: 31; width: parent.width - 125; elide: Text.ElideRight; text: picker.sourceLabel(row.modelData) + (row.modelData.saved_in_catalog ? picker.t(" · 已保存", " · Saved") : "") + (row.modelData.configured_model ? picker.t(" · 配置模型", " · Configured") : ""); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 9 }
                Rectangle {
                    visible: row.selected; x: parent.width - 87; y: 12; width: 49; height: 27; radius: 8
                    color: picker.defaultId === row.modelData.id ? "#ded9fa" : "#f4f3fa"
                    Text { anchors.centerIn: parent; text: picker.defaultId === row.modelData.id ? picker.t("默认", "Default") : picker.t("设默认", "Set default"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 9 }
                    MouseArea { anchors.fill: parent; enabled: !bridge.busy; onClicked: { picker.defaultId = row.modelData.id; picker.draftDirty = true } }
                }
                ToolButton {
                    x: parent.width - 34; y: 11; width: 30; height: 30; text: "···"
                    enabled: !bridge.busy && row.modelData.category !== "excluded"
                    onClicked: picker.openDetails(row.modelData.id)
                    contentItem: Text { text: parent.text; color: host.muted; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 17 }
                    background: Rectangle { radius: 8; color: parent.hovered ? "#eceafa" : "transparent" }
                    ToolTip.visible: hovered; ToolTip.text: picker.t("高级参数", "Advanced parameters")
                }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter; y: parent.height / 2 - 25; width: parent.width - 28; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                visible: modelList.count === 0
                text: !bridge.state.api_ready ? picker.t("先配置 API 地址和 Key。", "Set up your API URL and key first.") : !picker.entries.length ? picker.t("点击同步，获取当前 API 的模型名单。", "Refresh to discover this API's models.") : picker.scope === "selected" ? picker.t("草稿已勾选 ", "Draft selection: ") + picker.selectedIds.length + picker.t(" 个；当前搜索未匹配。", " models; none match this search.") : picker.t("当前筛选无匹配项，不代表 Codex 没有可用模型。", "No filter matches; this does not describe Codex availability.")
                color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 11
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height / 2 + 15; visible: modelList.count === 0 && search.text.length > 0; text: picker.t("清除搜索", "Clear search"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 11; MouseArea { anchors.fill: parent; onClicked: search.text = "" } }
        }
    }
    Text {
        y: parent.height - 54; width: parent.width - 80; elide: Text.ElideRight
        text: selectedIds.length ? t("草稿默认：", "Draft default: ") + defaultId : t("草稿尚未选择模型。", "No draft models selected.")
        color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 9
    }
    Text {
        visible: bridge.state.catalog_enabled; y: parent.height - 54; anchors.right: parent.right
        text: t("撤销目录", "Reset catalog"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 9
        MouseArea { anchors.fill: parent; enabled: !bridge.busy; onClicked: bridge.resetModels() }
    }
    Button {
        objectName: "applyModelButton"
        anchors.bottom: parent.bottom; width: parent.width; height: 38
        enabled: !bridge.busy && picker.selectedIds.length > 0
        onClicked: bridge.applySelection(JSON.stringify(picker.selectedIds), picker.defaultId)
        contentItem: Text { text: bridge.busy ? picker.t("正在处理…", "Working…") : picker.t("保存草稿 ", "Save draft: ") + picker.selectedIds.length + picker.t(" 个模型并切到 API", " models, use API"); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "white"; font.family: bridge.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
        background: Rectangle { radius: 11; color: host.accent; opacity: parent.enabled ? 1 : 0.4 }
    }

    Rectangle {
        id: statePanel; objectName: "modelStatePanel"; anchors.fill: parent; color: "#f7f8fc"; visible: false; z: 3
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(event) { event.accepted = true } }
        Text { text: picker.t("模型状态对照", "Model state comparison"); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
        Text { anchors.right: parent.right; y: 7; text: picker.t("返回", "Back"); color: host.accent; font.pixelSize: 11; MouseArea { anchors.fill: parent; onClicked: statePanel.visible = false } }
        Rectangle {
            y: 43; width: parent.width; height: 70; radius: 11; color: "white"; border.color: "#e2e5ef"
            Text { x: 12; y: 9; text: picker.t("全局配置 · 非当前会话", "Global config · not a running chat"); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { x: 12; y: 31; width: parent.width - 130; elide: Text.ElideRight; text: bridge.state.provider + " / " + (bridge.state.model || picker.t("默认模型", "Default model")); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 11 }
            Text { x: 12; y: 51; text: "config.toml"; color: host.muted; font.pixelSize: 9 }
            Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 32; text: picker.t("加入草稿", "Add to draft"); color: host.accent; font.pixelSize: 11; visible: picker.entries.some(m => m.id === bridge.state.model && m.category !== "excluded"); MouseArea { anchors.fill: parent; enabled: !bridge.busy; onClicked: picker.includeConfigured() } }
        }
        Rectangle {
            y: 120; width: parent.width; height: 70; radius: 11; color: "white"; border.color: "#e2e5ef"
            Text { x: 12; y: 9; text: picker.t("已保存目录 · 启动时加载", "Saved catalog · loaded at startup"); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { x: 12; y: 31; width: parent.width - 24; elide: Text.ElideRight; text: (bridge.state.saved_model_ids || []).join(", ") || picker.t("未使用工具目录", "No managed catalog"); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 11 }
            Text { x: 12; y: 51; text: bridge.state.catalog_configured ? picker.t("配置已引用，运行中是否加载仍未知", "Referenced in config; runtime loading is unknown") : picker.t("当前配置未启用此目录", "Not enabled in the current configuration"); color: host.muted; font.pixelSize: 9 }
        }
        Rectangle {
            y: 197; width: parent.width; height: 70; radius: 11; color: "#efecfc"
            Text { x: 12; y: 9; text: picker.t("编辑草稿 · 尚未写入", "Draft · not saved"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { x: 12; y: 31; width: parent.width - 24; elide: Text.ElideRight; text: picker.selectedIds.length + picker.t(" 个；默认 ", " models; default ") + picker.defaultId; color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 11 }
            Text { x: 12; y: 51; text: picker.t("返回列表后保存才会更改配置", "Return to the list and save to change config"); color: host.muted; font.pixelSize: 9 }
        }
        Rectangle {
            y: 274; width: parent.width; height: 78; radius: 11; color: "white"; border.color: "#e2e5ef"
            Text { x: 12; y: 9; text: picker.t("现有本机进程 · 独立检查", "Existing local server · independent check"); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 9; text: picker.t("检查", "Check"); color: host.accent; font.pixelSize: 11; MouseArea { anchors.fill: parent; enabled: !bridge.busy; onClicked: bridge.inspectRuntime() } }
            Text { x: 12; y: 30; width: parent.width - 24; wrapMode: Text.WordWrap; text: bridge.runtimeState.status === "connected" ? picker.t("读到上次进程目录 ", "Last server catalog: ") + bridge.runtimeState.models.length + picker.t(" 个；前台会话模型与计费连接仍未知。", " models; foreground chat model and billing route remain unknown.") : picker.t("当前会话模型 / 计费连接：未知。未接入桌面。", "Current chat model / billing route: unknown. Desktop is not connected."); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 10 }
            Text { x: 12; y: 61; width: parent.width - 24; elide: Text.ElideRight; text: bridge.runtimeState.checked_at || picker.t("尚未检查；不以配置值推断", "Not checked; never inferred from config"); color: host.muted; font.pixelSize: 9 }
        }
    }

    Rectangle {
        id: advanced; objectName: "advancedModelPanel"
        anchors.fill: parent; visible: false; color: "#f7f8fc"; z: 4
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(event) { event.accepted = true } }
        Text { text: picker.t("高级参数", "Advanced parameters"); color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
        Text { anchors.right: parent.right; y: 7; text: picker.t("返回列表", "Back to list"); color: host.accent; font.family: bridge.fontFamily; font.pixelSize: 11; MouseArea { anchors.fill: parent; onClicked: advanced.visible = false } }
        Text { y: 34; width: parent.width; elide: Text.ElideRight; text: picker.detailId; color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 12 }
        Text { y: 56; text: picker.detail ? picker.sourceLabel(picker.detail) : ""; color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
        Text { y: 83; text: picker.t("上下文 tokens（客户端预算，不会扩大模型上限）", "Context tokens (client budget, not model capacity)"); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
        TextField { id: contextInput; objectName: "gatewayContextField"; y: 103; width: parent.width; height: 34; selectByMouse: true; enabled: !bridge.busy; color: host.ink; font.pixelSize: 12; background: Rectangle { radius: 9; color: "white"; border.color: "#dfe3ee" } }
        Text { y: 149; text: picker.t("推理档位（逗号分隔；未知则留空）", "Reasoning levels (comma separated; blank if unknown)"); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
        TextField { id: reasoningInput; objectName: "gatewayReasoningField"; y: 169; width: parent.width; height: 34; selectByMouse: true; enabled: !bridge.busy; color: host.ink; font.pixelSize: 12; background: Rectangle { radius: 9; color: "white"; border.color: "#dfe3ee" } }
        CheckBox {
            id: imageInput; y: 213; height: 30; text: picker.t("接口确实支持图片输入", "The route supports image input"); enabled: !bridge.busy
            indicator: Rectangle { width: 18; height: 18; radius: 6; anchors.verticalCenter: parent.verticalCenter; color: imageInput.checked ? host.accent : "white"; border.color: imageInput.checked ? host.accent : "#ccd2e1"; Canvas { anchors.centerIn: parent; width: 12; height: 12; visible: imageInput.checked; onPaint: { const c=getContext("2d"); c.strokeStyle="white"; c.lineWidth=1.5; c.beginPath(); c.moveTo(2,6); c.lineTo(5,9); c.lineTo(10,3); c.stroke() } } }
            contentItem: Text { text: imageInput.text; leftPadding: 27; verticalAlignment: Text.AlignVCenter; color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 11 }
        }
        Text { y: 253; width: parent.width; wrapMode: Text.WordWrap; text: picker.t("仅在确认渠道能力后覆盖。基础模板的 32K / 仅文本是保守设置，并非检测结果。", "Override only confirmed capabilities. Basic 32K/text-only settings are a template, not detection."); color: host.muted; font.family: bridge.fontFamily; font.pixelSize: 10 }
        Button {
            anchors.bottom: parent.bottom; width: parent.width * 0.38; height: 38; text: picker.t("恢复默认", "Restore defaults"); enabled: !bridge.busy; onClicked: bridge.resetCapabilities(picker.detailId)
            contentItem: Text { text: parent.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: host.ink; font.family: bridge.fontFamily; font.pixelSize: 11 }
            background: Rectangle { radius: 10; color: "#eaeaf3" }
        }
        Button {
            objectName: "saveModelButton"; anchors.bottom: parent.bottom; anchors.right: parent.right; width: parent.width * 0.59; height: 38; text: picker.t("保存手动覆盖", "Save override"); enabled: !bridge.busy && picker.detail !== null; onClicked: bridge.configureModel(picker.detailId, picker.detail.enabled, contextInput.text, reasoningInput.text, imageInput.checked)
            contentItem: Text { text: parent.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "white"; font.family: bridge.fontFamily; font.pixelSize: 11 }
            background: Rectangle { radius: 10; color: host.accent; opacity: parent.enabled ? 1 : 0.4 }
        }
    }
}
