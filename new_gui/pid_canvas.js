const VIEW_WIDTH = 900;
const VIEW_HEIGHT = 650;
const plainCopy = (value) => JSON.parse(JSON.stringify(value));

export default {
  template: `
    <div class="pid-canvas-root" ref="root">
      <svg
        ref="canvas"
        class="pid-svg"
        :viewBox="'0 0 ' + viewWidth + ' ' + viewHeight"
        role="img"
        aria-label="Interactive P and ID canvas"
        @pointermove="handlePointerMove"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @click="clearSelection"
      >
        <defs>
          <pattern id="pid-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" class="pid-grid-dot" />
          </pattern>
        </defs>

        <rect width="100%" height="100%" class="pid-background" />
        <rect v-if="editable" width="100%" height="100%" fill="url(#pid-grid)" />

        <g class="pid-connections">
          <path
            v-for="edge in localConnections"
            :key="edge.id"
            :d="connectionPath(edge)"
            class="pid-pipe pid-pipe-pressurant"
          />
        </g>

        <g
          v-for="node in localComponents"
          :key="node.id"
          class="pid-node"
          :class="{ 'pid-node-selected': selectedId === node.id, 'pid-node-dragging': dragging && dragging.id === node.id }"
          :transform="nodeTransform(node)"
          @pointerdown="startDrag($event, node)"
          @pointerenter="showTooltip($event, node)"
          @pointermove="moveTooltip($event)"
          @pointerleave="hideTooltip"
          @click.stop="selectNode(node)"
        >
          <template v-if="node.kind === 'pressure_transducer'">
            <circle r="29" class="pid-symbol" />
            <text class="pid-symbol-letter" text-anchor="middle" dominant-baseline="central">P</text>
            <text x="0" y="48" class="pid-tag" text-anchor="middle">{{ node.tag }}</text>
            <text x="0" y="64" class="pid-reading" text-anchor="middle">{{ formattedValue(node) }}</text>
          </template>

          <template v-else-if="node.kind === 'thermocouple'">
            <circle r="29" class="pid-symbol" />
            <text class="pid-symbol-letter" text-anchor="middle" dominant-baseline="central">T</text>
            <text x="0" y="48" class="pid-tag" text-anchor="middle">{{ node.tag }}</text>
            <text x="0" y="64" class="pid-reading" text-anchor="middle">{{ formattedValue(node) }}</text>
          </template>

          <template v-else-if="node.kind === 'solenoid_valve'">
            <path d="M -42 -27 L 0 0 L -42 27 Z M 42 -27 L 0 0 L 42 27 Z" class="pid-valve-body" />
            <line x1="0" y1="-35" x2="0" y2="-55" class="pid-symbol-line" />
            <rect x="-11" y="-73" width="22" height="18" class="pid-coil" />
            <text x="0" y="-60" class="pid-coil-letter" text-anchor="middle">S</text>
            <text x="0" y="48" class="pid-tag" text-anchor="middle">{{ node.tag }}</text>
            <text x="0" y="65" class="pid-reading" text-anchor="middle">{{ node.value }}</text>
          </template>

          <template v-else-if="node.kind === 'tank'">
            <rect x="-50" y="-92" width="100" height="184" rx="45" class="pid-symbol pid-tank" />
            <text class="pid-tank-label" text-anchor="middle" dominant-baseline="central" transform="rotate(90)">{{ node.title.replace(' supply tank', '') }}</text>
            <text x="0" y="116" class="pid-tag" text-anchor="middle">{{ node.tag }}</text>
            <text x="0" y="134" class="pid-reading" text-anchor="middle">{{ formattedValue(node) }}</text>
          </template>

          <circle
            v-for="port in node.ports"
            :key="port.id"
            :cx="portPosition(node, port).x"
            :cy="portPosition(node, port).y"
            r="7"
            class="pid-port"
            :class="{ 'pid-port-pending': pendingPort && pendingPort.nodeId === node.id && pendingPort.portId === port.id }"
            @pointerdown.stop
            @click.stop="choosePort(node, port)"
          />
        </g>
      </svg>

      <div v-if="tooltipNode" class="pid-tooltip" :style="tooltipStyle" role="tooltip">
        <div class="pid-tooltip-title">{{ tooltipNode.tag }}</div>
        <div>{{ tooltipNode.title }}</div>
        <dl>
          <template v-if="tooltipNode.value !== null && tooltipNode.value !== undefined">
            <dt>{{ tooltipNode.kind === 'solenoid_valve' ? 'State' : 'Reading' }}</dt>
            <dd>{{ formattedValue(tooltipNode) }}</dd>
          </template>
          <template v-if="tooltipNode.channel">
            <dt>Channel</dt><dd>{{ tooltipNode.channel }}</dd>
          </template>
          <dt>Quality</dt><dd>{{ tooltipNode.quality }}</dd>
        </dl>
        <div v-if="tooltipNode.notes" class="pid-tooltip-note">{{ tooltipNode.notes }}</div>
      </div>

      <div class="pid-canvas-hint">
        {{ editable ? (pendingPort ? 'Select a second port to create a connection' : 'Drag components · select two ports to connect') : 'Live view · layout locked' }}
      </div>
    </div>
  `,

  props: {
    components: { type: Array, default: () => [] },
    connections: { type: Array, default: () => [] },
    editable: { type: Boolean, default: true },
  },

  data() {
    return {
      viewWidth: VIEW_WIDTH,
      viewHeight: VIEW_HEIGHT,
      localComponents: this.components.map(plainCopy),
      localConnections: this.connections.map(plainCopy),
      dragging: null,
      selectedId: null,
      pendingPort: null,
      tooltipNode: null,
      tooltipX: 0,
      tooltipY: 0,
    };
  },

  watch: {
    editable(value) {
      if (!value) {
        this.dragging = null;
        this.pendingPort = null;
      }
    },
  },

  computed: {
    tooltipStyle() {
      return { left: this.tooltipX + 'px', top: this.tooltipY + 'px' };
    },
  },

  methods: {
    addComponent(component) {
      this.localComponents.push(plainCopy(component));
    },

    setComponentState(componentId, changes) {
      const component = this.localComponents.find((item) => item.id === componentId);
      if (component) Object.assign(component, changes);
    },

    nodeTransform(node) {
      return 'translate(' + node.x + ' ' + node.y + ') rotate(' + (node.rotation || 0) + ')';
    },

    dimensions(node) {
      if (node.kind === 'tank') return { halfWidth: 50, halfHeight: 92 };
      if (node.kind === 'solenoid_valve') return { halfWidth: 42, halfHeight: 27 };
      return { halfWidth: 29, halfHeight: 29 };
    },

    portPosition(node, port) {
      const size = this.dimensions(node);
      if (port.side === 'top') return { x: 0, y: -size.halfHeight };
      if (port.side === 'bottom') return { x: 0, y: size.halfHeight };
      if (port.side === 'left') return { x: -size.halfWidth, y: 0 };
      return { x: size.halfWidth, y: 0 };
    },

    absolutePort(componentId, portId) {
      const node = this.localComponents.find((item) => item.id === componentId);
      if (!node) return null;
      const port = node.ports.find((item) => item.id === portId);
      if (!port) return null;
      const relative = this.portPosition(node, port);
      return { x: node.x + relative.x, y: node.y + relative.y, side: port.side };
    },

    connectionPath(edge) {
      const source = this.absolutePort(edge.source_component, edge.source_port);
      const target = this.absolutePort(edge.target_component, edge.target_port);
      if (!source || !target) return '';
      const dx = Math.abs(target.x - source.x);
      const dy = Math.abs(target.y - source.y);
      if (dy >= dx) {
        const middleY = (source.y + target.y) / 2;
        return 'M ' + source.x + ' ' + source.y + ' V ' + middleY + ' H ' + target.x + ' V ' + target.y;
      }
      const middleX = (source.x + target.x) / 2;
      return 'M ' + source.x + ' ' + source.y + ' H ' + middleX + ' V ' + target.y + ' H ' + target.x;
    },

    svgPoint(event) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left) * this.viewWidth / rect.width,
        y: (event.clientY - rect.top) * this.viewHeight / rect.height,
      };
    },

    startDrag(event, node) {
      if (!this.editable || event.button !== 0) return;
      const point = this.svgPoint(event);
      this.dragging = { id: node.id, pointerId: event.pointerId, dx: point.x - node.x, dy: point.y - node.y };
      this.$refs.canvas.setPointerCapture(event.pointerId);
    },

    handlePointerMove(event) {
      if (!this.dragging) return;
      const node = this.localComponents.find((item) => item.id === this.dragging.id);
      if (!node) return;
      const point = this.svgPoint(event);
      node.x = Math.max(70, Math.min(this.viewWidth - 70, point.x - this.dragging.dx));
      node.y = Math.max(90, Math.min(this.viewHeight - 110, point.y - this.dragging.dy));
    },

    endDrag(event) {
      if (!this.dragging) return;
      const node = this.localComponents.find((item) => item.id === this.dragging.id);
      if (node) this.$emit('component-moved', { id: node.id, x: node.x, y: node.y });
      if (this.$refs.canvas.hasPointerCapture(event.pointerId)) this.$refs.canvas.releasePointerCapture(event.pointerId);
      this.dragging = null;
    },

    selectNode(node) {
      this.selectedId = node.id;
      this.$emit('component-selected', { id: node.id });
    },

    clearSelection() {
      this.selectedId = null;
      this.pendingPort = null;
    },

    choosePort(node, port) {
      if (!this.editable) return;
      const selected = { nodeId: node.id, portId: port.id };
      if (!this.pendingPort) {
        this.pendingPort = selected;
        return;
      }
      if (this.pendingPort.nodeId === selected.nodeId && this.pendingPort.portId === selected.portId) {
        this.pendingPort = null;
        return;
      }
      const edge = {
        id: 'pipe-ui-' + Date.now(),
        source_component: this.pendingPort.nodeId,
        source_port: this.pendingPort.portId,
        target_component: selected.nodeId,
        target_port: selected.portId,
        medium: 'pressurant',
      };
      this.localConnections.push(edge);
      this.$emit('connection-created', edge);
      this.pendingPort = null;
    },

    showTooltip(event, node) {
      this.tooltipNode = node;
      this.moveTooltip(event);
    },

    moveTooltip(event) {
      if (!this.tooltipNode) return;
      const rect = this.$refs.root.getBoundingClientRect();
      this.tooltipX = Math.min(rect.width - 270, Math.max(12, event.clientX - rect.left + 16));
      this.tooltipY = Math.min(rect.height - 185, Math.max(12, event.clientY - rect.top + 16));
    },

    hideTooltip() {
      this.tooltipNode = null;
    },

    formattedValue(node) {
      if (node.value === null || node.value === undefined || node.value === '') return 'No reading';
      if (typeof node.value === 'number') return node.value.toFixed(1) + (node.units ? ' ' + node.units : '');
      return String(node.value) + (node.units ? ' ' + node.units : '');
    },
  },
};

