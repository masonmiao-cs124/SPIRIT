// JavaScript companion for the original PidCanvas Python class.
// Keep this file in the same folder as pid_canvas.py.

const copy = value => JSON.parse(JSON.stringify(value));

export default {
  // Values received from the Python PidCanvas class.
  props: {
    components: {
      type: Array,
      default: () => [],
    },
    connections: {
      type: Array,
      default: () => [],
    },
    editable: {
      type: Boolean,
      default: true,
    },
  },

  // Events sent back to Python.
  emits: [
    'component-moved',
    'component-selected',
    'connection-created',
  ],

  // Browser-side state.
  data() {
    return {
      nodes: copy(this.components),
      pipes: copy(this.connections),

      lastComponents: JSON.stringify(this.components),
      lastConnections: JSON.stringify(this.connections),

      selected: null,
      pending: null,
      dragging: null,
      hoverId: null,

      tooltipX: 0,
      tooltipY: 0,

      message: '',
      connectionCounter: 0,
    };
  },

  // Respond to property updates from Python.
  watch: {
    components: {
      deep: true,

      handler(value) {
        const signature = JSON.stringify(value);

        // The original Python wrapper retains its initial props while
        // updates arrive through run_method. Avoid resetting those
        // updates when Edit mode changes.
        if (signature === this.lastComponents) {
          return;
        }

        this.lastComponents = signature;

        for (const node of value) {
          this.addComponent(node);
        }
      },
    },

    connections: {
      deep: true,

      handler(value) {
        const signature = JSON.stringify(value);

        if (signature === this.lastConnections) {
          return;
        }

        this.lastConnections = signature;

        for (const pipe of value) {
          const existing = this.pipes.find(
            p => p.id === pipe.id
          );

          if (existing) {
            Object.assign(existing, copy(pipe));
          } else {
            this.pipes.push(copy(pipe));
          }
        }
      },
    },

    editable(value) {
      if (!value) {
        this.pending = null;
        this.dragging = null;
      }
    },
  },

  computed: {
    hovered() {
      return this.nodes.find(
        n => n.id === this.hoverId
      );
    },
  },

  methods: {
    // Called by Python:
    // self.run_method("addComponent", component.as_dict())
    addComponent(component) {
      const existing = this.nodes.find(
        n => n.id === component.id
      );

      if (existing) {
        Object.assign(existing, copy(component));
      } else {
        this.nodes.push(copy(component));
      }
    },

    // Called by Python:
    // self.run_method("setComponentState", component_id, changes)
    setComponentState(componentId, changes) {
      const node = this.nodes.find(
        n => n.id === componentId
      );

      if (node) {
        Object.assign(node, changes);
      }
    },

    // Half of each symbol's width and height.
    halfSize(node) {
      if (node.kind === 'tank') {
        return { x: 42, y: 64 };
      }

      if (node.kind === 'solenoid_valve') {
        return { x: 28, y: 25 };
      }

      return { x: 25, y: 25 };
    },

    // Port coordinates relative to the component's center.
    localPort(node, port) {
      const size = this.halfSize(node);

      const positions = {
        left: {
          x: -size.x,
          y: 0,
        },
        right: {
          x: size.x,
          y: 0,
        },
        top: {
          x: 0,
          y: -size.y,
        },
        bottom: {
          x: 0,
          y: size.y,
        },
      };

      return positions[port.side] || { x: 0, y: 0 };
    },

    // Convert a component port into diagram coordinates.
    // Rotation is included in the calculation.
    endpoint(componentId, portId) {
      const node = this.nodes.find(
        n => n.id === componentId
      );

      const port = node?.ports.find(
        p => p.id === portId
      );

      if (!port) {
        return null;
      }

      const local = this.localPort(node, port);

      const directions = {
        left: [-1, 0],
        right: [1, 0],
        top: [0, -1],
        bottom: [0, 1],
      };

      const direction = directions[port.side] || [0, 0];

      const angle = (node.rotation || 0) * Math.PI / 180;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      return {
        x: node.x + local.x * cos - local.y * sin,
        y: node.y + local.x * sin + local.y * cos,

        dx: direction[0] * cos - direction[1] * sin,
        dy: direction[0] * sin + direction[1] * cos,
      };
    },

    // Generate an SVG path with right-angle bends.
    pipePath(pipe) {
      const start = this.endpoint(
        pipe.source_component,
        pipe.source_port
      );

      const end = this.endpoint(
        pipe.target_component,
        pipe.target_port
      );

      if (!start || !end) {
        return '';
      }

      // Short straight segments extending out from each port.
      const a = {
        x: start.x + 24 * start.dx,
        y: start.y + 24 * start.dy,
      };

      const b = {
        x: end.x + 24 * end.dx,
        y: end.y + 24 * end.dy,
      };

      let elbows;

      if (
        Math.abs(start.dx) > 0.5 &&
        Math.abs(end.dx) > 0.5
      ) {
        const x = (a.x + b.x) / 2;

        elbows = [
          { x, y: a.y },
          { x, y: b.y },
        ];
      } else if (
        Math.abs(start.dy) > 0.5 &&
        Math.abs(end.dy) > 0.5
      ) {
        const y = (a.y + b.y) / 2;

        elbows = [
          { x: a.x, y },
          { x: b.x, y },
        ];
      } else if (Math.abs(start.dx) > 0.5) {
        elbows = [
          { x: b.x, y: a.y },
        ];
      } else {
        elbows = [
          { x: a.x, y: b.y },
        ];
      }

      return [start, a, ...elbows, b, end]
        .map(
          (point, index) =>
            `${index ? 'L' : 'M'} ${point.x} ${point.y}`
        )
        .join(' ');
    },

    // Format a sensor reading or valve command.
    reading(node) {
      if (node.kind === 'solenoid_valve') {
        if (node.commanded_open == null) {
          return 'Command unknown';
        }

        return `Command: ${
          node.commanded_open ? 'OPEN' : 'CLOSED'
        }`;
      }

      if (node.value == null) {
        return 'No reading';
      }

      const value =
        typeof node.value === 'number'
          ? node.value.toFixed(1)
          : node.value;

      return `${value}${node.units ? ' ' + node.units : ''}`;
    },

    // Position the tag below the symbol.
    labelY(node) {
      return this.halfSize(node).y + 22;
    },

    // Convert mouse/screen coordinates to SVG coordinates.
    point(event) {
      return new DOMPoint(
        event.clientX,
        event.clientY
      ).matrixTransform(
        this.$refs.svg.getScreenCTM().inverse()
      );
    },

    // Select a component and optionally begin dragging.
    select(event, node) {
      if (event.button !== 0) {
        return;
      }

      this.selected = node.id;
      this.message = '';

      this.$emit('component-selected', {
        id: node.id,
      });

      this.$refs.root.focus();

      if (!this.editable) {
        return;
      }

      const p = this.point(event);

      this.dragging = {
        id: node.id,
        dx: node.x - p.x,
        dy: node.y - p.y,
        moved: false,
      };

      this.hoverId = null;

      this.$refs.svg.setPointerCapture(
        event.pointerId
      );
    },

    // Update a component's position while dragging.
    move(event) {
      if (!this.dragging) {
        return;
      }

      const node = this.nodes.find(
        n => n.id === this.dragging.id
      );

      const p = this.point(event);

      node.x = Math.max(
        65,
        Math.min(
          930,
          Math.round(p.x + this.dragging.dx)
        )
      );

      node.y = Math.max(
        60,
        Math.min(
          560,
          Math.round(p.y + this.dragging.dy)
        )
      );

      this.dragging.moved = true;
    },

    // Finish dragging and send the new coordinates to Python.
    finish(event) {
      if (this.dragging?.moved) {
        const node = this.nodes.find(
          n => n.id === this.dragging.id
        );

        this.$emit('component-moved', {
          id: node.id,
          x: node.x,
          y: node.y,
        });
      }

      this.dragging = null;

      if (
        this.$refs.svg.hasPointerCapture(
          event.pointerId
        )
      ) {
        this.$refs.svg.releasePointerCapture(
          event.pointerId
        );
      }
    },

    // Count connections already attached to a port.
    used(component, port) {
      return this.pipes.filter(
        p =>
          (
            p.source_component === component &&
            p.source_port === port
          ) ||
          (
            p.target_component === component &&
            p.target_port === port
          )
      ).length;
    },

    // Clicking one port starts a connection.
    // Clicking a second port completes it.
    connect(node, port) {
      if (!this.editable) {
        return;
      }

      this.message = '';

      if (
        this.used(node.id, port.id) >=
        (port.max_connections ?? 1)
      ) {
        this.message =
          'This port has reached its connection limit.';
        return;
      }

      if (!this.pending) {
        this.pending = {
          component: node.id,
          port: port.id,
          kind: port.kind,
        };

        return;
      }

      const source = this.pending;
      this.pending = null;

      if (source.component === node.id) {
        this.message = 'Choose a different component.';
        return;
      }

      if (source.kind !== port.kind) {
        this.message =
          'The ports must have the same kind.';
        return;
      }

      const duplicate = this.pipes.some(
        p =>
          (
            p.source_component === source.component &&
            p.source_port === source.port &&
            p.target_component === node.id &&
            p.target_port === port.id
          ) ||
          (
            p.target_component === source.component &&
            p.target_port === source.port &&
            p.source_component === node.id &&
            p.source_port === port.id
          )
      );

      if (duplicate) {
        this.message =
          'These ports are already connected.';
        return;
      }

      const pipe = {
        id: `pipe-web-${Date.now()}-${++this.connectionCounter}`,
        source_component: source.component,
        source_port: source.port,
        target_component: node.id,
        target_port: port.id,
        medium: 'pressurant',
      };

      this.pipes.push(pipe);

      this.$emit(
        'connection-created',
        copy(pipe)
      );
    },

    // Position the hover tooltip inside the canvas.
    tooltip(event, node) {
      if (this.dragging) {
        return;
      }

      this.hoverId = node.id;

      const rect =
        this.$refs.root.getBoundingClientRect();

      this.tooltipX = Math.max(
        0,
        Math.min(
          event.clientX - rect.left + 16,
          rect.width - 285
        )
      );

      this.tooltipY = Math.max(
        0,
        Math.min(
          event.clientY - rect.top + 16,
          rect.height - 220
        )
      );
    },
  },

  // Vue template: draws the diagram using SVG.
  template: `
    <div
      ref="root"
      class="pid-canvas-root"
      tabindex="0"
      style="position:relative; outline:none"
      @keydown.esc="
        pending = null;
        message = '';
        hoverId = null
      "
    >
      <svg
        ref="svg"
        class="pid-svg"
        viewBox="0 0 1000 680"
        role="img"
        aria-label="GN2 pressurant piping diagram"
        @pointermove="move"
        @pointerup="finish"
        @pointercancel="finish"
        @pointerdown.self="
          pending = null;
          message = ''
        "
      >
        <defs>
          <pattern
            :id="'pid-grid-' + $.uid"
            width="25"
            height="25"
            patternUnits="userSpaceOnUse"
          >
            <circle
              cx="1"
              cy="1"
              r="1"
              class="pid-grid-dot"
            />
          </pattern>
        </defs>

        <!-- Background -->
        <rect
          width="1000"
          height="680"
          class="pid-background"
          @pointerdown="
            pending = null;
            message = ''
          "
        />

        <!-- Grid -->
        <rect
          width="1000"
          height="680"
          :fill="'url(#pid-grid-' + $.uid + ')'"
          pointer-events="none"
        />

        <!-- Fluid connections -->
        <g
          class="pid-pipes"
          pointer-events="none"
        >
          <path
            v-for="pipe in pipes"
            :key="pipe.id"
            :data-connection-id="pipe.id"
            :d="pipePath(pipe)"
            class="pid-pipe pid-pipe-pressurant"
          />
        </g>

        <!-- Components -->
        <g
          v-for="node in nodes"
          :key="node.id"
          :data-component-id="node.id"
          :transform="
            'translate(' + node.x + ',' + node.y + ')'
          "
          class="pid-node"
          :class="{
            'pid-node-selected': selected === node.id,
            'pid-node-dragging': dragging?.id === node.id
          }"
          @pointerdown.stop="select($event, node)"
          @pointerenter="tooltip($event, node)"
          @pointerleave="hoverId = null"
        >
          <title>
            {{ node.tag }} — {{ node.title }}
          </title>

          <g
            :transform="
              'rotate(' + (node.rotation || 0) + ')'
            "
            class="pid-shape"
          >
            <!-- Tank -->
            <template v-if="node.kind === 'tank'">
              <rect
                x="-42"
                y="-64"
                width="84"
                height="128"
                rx="35"
                class="pid-symbol"
              />

              <text
                y="7"
                text-anchor="middle"
                class="pid-tank-label"
              >
                GN₂
              </text>
            </template>

            <!-- Solenoid valve -->
            <template
              v-else-if="node.kind === 'solenoid_valve'"
            >
              <path
                d="M -28 -25 H 28 L -28 25 H 28 Z"
                class="pid-valve-body"
              />

              <path
                d="M 28 0 H 45"
                class="pid-symbol-line"
              />

              <rect
                x="38"
                y="-10"
                width="20"
                height="20"
                class="pid-coil"
              />

              <text
                x="48"
                y="4"
                text-anchor="middle"
                class="pid-coil-letter"
              >
                S
              </text>
            </template>

            <!-- Pressure transducer or thermocouple -->
            <template v-else>
              <circle
                r="25"
                class="pid-symbol"
              />

              <text
                y="8"
                text-anchor="middle"
                class="pid-symbol-letter"
              >
                {{ node.kind === 'thermocouple' ? 'T' : 'P' }}
              </text>
            </template>

            <!-- Connection handles -->
            <circle
              v-for="port in (editable ? node.ports : [])"
              :key="port.id"
              :data-port="port.id"
              :cx="localPort(node, port).x"
              :cy="localPort(node, port).y"
              r="6"
              class="pid-port"
              :class="{
                'pid-port-pending':
                  pending?.component === node.id &&
                  pending?.port === port.id
              }"
              @pointerdown.stop=""
              @click.stop="connect(node, port)"
            >
              <title>{{ port.id }}</title>
            </circle>
          </g>

          <!-- Component tag -->
          <text
            :y="labelY(node)"
            text-anchor="middle"
            class="pid-tag"
          >
            {{ node.tag }}
          </text>

          <!-- Reading or command state -->
          <text
            :y="labelY(node) + 18"
            text-anchor="middle"
            class="pid-reading"
          >
            {{ reading(node) }}
          </text>
        </g>
      </svg>

      <!-- Editing instructions or validation message -->
      <div class="pid-canvas-hint">
        {{
          message ||
          (
            pending
              ? 'Select a second port · Esc cancels'
              : editable
                ? 'Drag components · hover to see ports · click two ports to connect'
                : 'View mode · hover or click a component for details'
          )
        }}
      </div>

      <!-- Hover details -->
      <div
        v-if="hovered"
        class="pid-tooltip"
        :style="{
          left: tooltipX + 'px',
          top: tooltipY + 'px'
        }"
      >
        <div class="pid-tooltip-title">
          {{ hovered.tag }}
        </div>

        <div>
          {{ hovered.title }}
        </div>

        <dl>
          <dt>Reading</dt>
          <dd>{{ reading(hovered) }}</dd>

          <dt>Channel</dt>
          <dd>{{ hovered.channel || 'Unassigned' }}</dd>

          <dt>Quality</dt>
          <dd>{{ hovered.quality || 'Unknown' }}</dd>
        </dl>

        <div
          v-if="hovered.notes"
          class="pid-tooltip-note"
        >
          {{ hovered.notes }}
        </div>
      </div>
    </div>
  `,
};