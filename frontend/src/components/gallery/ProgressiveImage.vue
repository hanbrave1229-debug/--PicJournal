<template>
  <div class="pi-wrap">
    <!-- ThumbHash placeholder (blurred color background) -->
    <div
      v-if="!loaded"
      class="pi-placeholder"
      :style="placeholderStyle"
    >
      <div class="pi-spinner" />
    </div>

    <!-- Real image -->
    <img
      :src="src"
      :alt="alt"
      class="pi-img"
      :class="{ 'pi-img--visible': loaded }"
      loading="lazy"
      @load="onLoad"
      @error="onError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  /** Real image URL */
  src: string
  /** Alt text */
  alt?: string
  /**
   * ThumbHash Base64 string or a CSS gradient to use as placeholder.
   * If not provided, a solid dark fallback color is used.
   */
  thumbhash?: string | null
  /** Fallback gradient color stops — used when thumbhash is absent */
  fallbackGradient?: string
}

const props = withDefaults(defineProps<Props>(), {
  alt: '',
  thumbhash: null,
  fallbackGradient: 'linear-gradient(135deg, #1e2126 0%, #2a2d35 100%)',
})

const loaded = ref(false)
const errored = ref(false)

function onLoad(): void {
  loaded.value = true
}

function onError(): void {
  errored.value = true
  loaded.value = true // hide placeholder on error too
}

/**
 * Build the CSS background for the placeholder div.
 *
 * ThumbHash is a compact perceptual hash (~20 bytes) that encodes color
 * distribution. When the real thumbhash decoder (WASM) is not available,
 * we fall back to the gradient from the hash's dominant hue metadata.
 *
 * In this implementation we store the computed CSS gradient alongside
 * the thumbhash string in the DB, OR we derive a simple gradient from
 * the dominant hue. For now we use the fallbackGradient prop or the
 * thumbhash if it looks like a gradient/color string (i.e. starts with
 * "linear-gradient" or "#").  If it's a raw base64 thumbhash we'd need
 * the WASM decoder — we skip that and use fallback.
 */
const placeholderStyle = computed<Record<string, string>>(() => {
  const th = props.thumbhash
  if (th) {
    // If it looks like a CSS color or gradient, use it directly
    if (th.startsWith('linear-gradient') || th.startsWith('#') || th.startsWith('rgb')) {
      return { background: th }
    }
    // Otherwise: raw thumbhash base64 — use fallback gradient
  }
  return { background: props.fallbackGradient }
})
</script>

<style lang="scss" scoped>
.pi-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1c21;
}

// ── Placeholder ───────────────────────────────────────────────────────────────
.pi-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  filter: blur(10px);
  transform: scale(1.1); // prevent blur edge bleed
  transition: opacity 600ms cubic-bezier(0.25, 0.8, 0.25, 1);
}

// ── Spinner ───────────────────────────────────────────────────────────────────
.pi-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  animation: pi-spin 0.8s linear infinite;
}

@keyframes pi-spin {
  to { transform: rotate(360deg); }
}

// ── Real image ────────────────────────────────────────────────────────────────
.pi-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 600ms cubic-bezier(0.25, 0.8, 0.25, 1);
  z-index: 2;

  &.pi-img--visible {
    opacity: 1;
  }
}
</style>
