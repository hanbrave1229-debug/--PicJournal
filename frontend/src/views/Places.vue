<script setup lang="ts">
/**
 * Places.vue — Browse photos grouped by city.
 * Tile grid of city cards → click → city photo wall.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/index'
import ImageViewer from '@/components/gallery/ImageViewer.vue'

// ── Types ────────────────────────────────────────────────────────────────────

interface CityItem {
  country: string | null
  province: string | null
  city: string
  photo_count: number
  cover_thumbnail: string | null
}

interface PlacePhoto {
  id: number
  thumbnail_url: string | null   // /api/v1/thumbnails/{id}?size=256
  taken_at: string | null
  city: string | null
  province: string | null
  country: string | null
  ai_caption: string | null
}

// ── State ────────────────────────────────────────────────────────────────────

const route  = useRoute()
const router = useRouter()

const cities      = ref<CityItem[]>([])
const loading     = ref(false)
const activeCity  = ref<string | null>(null)
const cityPhotos  = ref<PlacePhoto[]>([])
const photoLoading = ref(false)
const page        = ref(1)
const hasMore     = ref(true)
const searchQ     = ref('')

// ImageViewer
const viewerVisible = ref(false)
const viewerIndex   = ref(0)

// ── Computed ─────────────────────────────────────────────────────────────────

const filteredCities = computed(() => {
  const q = searchQ.value.trim().toLowerCase()
  if (!q) return cities.value
  return cities.value.filter(c =>
    c.city.toLowerCase().includes(q) ||
    (c.province ?? '').toLowerCase().includes(q) ||
    (c.country ?? '').toLowerCase().includes(q)
  )
})

const activeCityInfo = computed(() =>
  cities.value.find(c => c.city === activeCity.value) ?? null
)

/** Deduplicated viewer-ready photos */
const viewerPhotos = computed(() =>
  cityPhotos.value.map(p => ({
    id: p.id,
    thumbnail_256: p.thumbnail_url,
    thumbnail_1080: null,
    file_path: '',
    file_name: '',
    file_ext: '',
    file_size: 0,
    width: null,
    height: null,
    md5_hash: null,
    phash: null,
    thumbhash: null,
    is_deleted: false,
    duplicate_group_id: null,
    exif: { taken_at: p.taken_at, camera_make: null, camera_model: null, aperture: null, shutter_speed: null, iso: null, gps_lat: null, gps_lon: null },
    scores: { sharpness_score: null, exposure_score: null },
    ai_caption: p.ai_caption,
    ai_tags: [],
    country: p.country,
    province: p.province,
    city: p.city,
    is_archived: false,
    stack_id: null,
    is_stack_cover: false,
    created_at: p.taken_at ?? '',
    updated_at: p.taken_at ?? '',
  }))
)

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchCities() {
  loading.value = true
  try {
    const res = await api.get<CityItem[]>('/geocoding/cities')
    cities.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadCityPhotos(city: string, reset = true) {
  if (reset) { cityPhotos.value = []; page.value = 1; hasMore.value = true }
  if (!hasMore.value) return
  photoLoading.value = true
  try {
    const res = await api.get<PlacePhoto[]>('/geocoding/photos', { params: { city, page: page.value, page_size: 60 } })
    cityPhotos.value.push(...res.data)
    if (res.data.length < 60) hasMore.value = false
    else page.value++
  } finally {
    photoLoading.value = false
  }
}

function selectCity(city: string) {
  activeCity.value = city
  router.replace({ name: 'places', query: { city } })
  loadCityPhotos(city)
}

function backToList() {
  activeCity.value = null
  cityPhotos.value = []
  router.replace({ name: 'places' })
}

// ImageViewer
function openViewer(index: number) {
  viewerIndex.value = index
  viewerVisible.value = true
}

function navigateViewer(delta: 1 | -1) {
  const next = viewerIndex.value + delta
  if (next >= 0 && next < cityPhotos.value.length) {
    viewerIndex.value = next
    // lazy-load more
    if (next >= cityPhotos.value.length - 10 && hasMore.value && activeCity.value) {
      loadCityPhotos(activeCity.value, false)
    }
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await fetchCities()
  const q = route.query.city as string | undefined
  if (q) selectCity(q)
})

watch(() => route.query.city, (c) => {
  if (c && c !== activeCity.value) selectCity(c as string)
  else if (!c && activeCity.value) backToList()
})
</script>

<template>
  <div class="pl-root">

    <!-- ── City list view ─────────────────────────────────────── -->
    <template v-if="!activeCity">
      <header class="pl-header">
        <h1 class="pl-title">地点</h1>
        <el-input
          v-model="searchQ"
          placeholder="搜索城市…"
          prefix-icon="Search"
          clearable
          class="pl-search"
        />
      </header>

      <div v-if="loading" class="pl-loading">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="filteredCities.length === 0" class="pl-empty">
        <el-empty description="暂无地点数据，扫描含 GPS 信息的照片后自动生成" />
      </div>

      <div v-else class="pl-city-grid">
        <div
          v-for="city in filteredCities"
          :key="city.city"
          class="pl-city-card"
          @click="selectCity(city.city)"
        >
          <div class="pl-city-thumb">
            <img
              v-if="city.cover_thumbnail"
              :src="city.cover_thumbnail"
              :alt="city.city"
              loading="lazy"
            />
            <div v-else class="pl-city-thumb--empty">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                <circle cx="12" cy="9" r="2.5"/>
              </svg>
            </div>
            <span class="pl-city-count">{{ city.photo_count }} 张</span>
          </div>
          <div class="pl-city-info">
            <span class="pl-city-name">{{ city.city }}</span>
            <span class="pl-city-sub">
              <template v-if="city.province && city.province !== city.city">{{ city.province }} · </template>
              {{ city.country }}
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- ── City detail view ───────────────────────────────────── -->
    <template v-else>
      <header class="pl-header pl-header--detail">
        <button class="pl-back" @click="backToList">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          全部地点
        </button>
        <div class="pl-detail-title">
          <h1 class="pl-title">{{ activeCity }}</h1>
          <span v-if="activeCityInfo" class="pl-detail-meta">
            {{ activeCityInfo.province ? activeCityInfo.province + ' · ' : '' }}{{ activeCityInfo.country }}
            &nbsp;·&nbsp;{{ activeCityInfo.photo_count }} 张照片
          </span>
        </div>
      </header>

      <div v-if="photoLoading && cityPhotos.length === 0" class="pl-loading">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="cityPhotos.length === 0" class="pl-empty">
        <el-empty description="该城市暂无照片" />
      </div>

      <div v-else class="pl-photo-grid">
        <div
          v-for="(photo, idx) in cityPhotos"
          :key="photo.id"
          class="pl-photo-item"
          @click="openViewer(idx)"
        >
          <img
            v-if="photo.thumbnail_url"
            :src="photo.thumbnail_url"
            :alt="photo.ai_caption ?? ''"
            loading="lazy"
          />
          <div v-else class="pl-photo-item--empty" />
          <span v-if="photo.taken_at" class="pl-photo-date">
            {{ new Date(photo.taken_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) }}
          </span>
        </div>

        <!-- Load more sentinel -->
        <div v-if="hasMore" class="pl-load-more">
          <el-button :loading="photoLoading" text @click="loadCityPhotos(activeCity!, false)">
            加载更多
          </el-button>
        </div>
      </div>
    </template>

    <!-- ImageViewer -->
    <ImageViewer
      v-if="viewerVisible && viewerPhotos.length"
      :visible="viewerVisible"
      :photo="viewerPhotos[viewerIndex]"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < viewerPhotos.length - 1"
      @close="viewerVisible = false"
      @navigate="navigateViewer"
    />
  </div>
</template>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────── */
.pl-root {
  height: 100%;
  overflow-y: auto;
  padding: 0 24px 40px;
  box-sizing: border-box;
}

/* ── Header ──────────────────────────────────────────────────────── */
.pl-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 0 16px;
  position: sticky;
  top: 0;
  background: var(--no-bg-base);
  z-index: 10;
}

.pl-header--detail {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.pl-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--no-text-primary);
  flex-shrink: 0;
}

.pl-search {
  max-width: 240px;
  margin-left: auto;
}

.pl-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.pl-detail-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.pl-detail-meta {
  font-size: 12px;
  color: var(--no-text-secondary);
}

/* ── City grid ───────────────────────────────────────────────────── */
.pl-city-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.pl-city-card {
  border-radius: 12px;
  overflow: hidden;
  background: var(--no-bg-surface);
  border: 1px solid var(--no-border-low);
  cursor: pointer;
  transition: transform 0.18s, box-shadow 0.18s;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  }
}

.pl-city-thumb {
  position: relative;
  aspect-ratio: 4 / 3;
  background: var(--no-bg-elevated);
  overflow: hidden;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.3s;
  }

  &:hover img { transform: scale(1.04); }
}

.pl-city-thumb--empty {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--no-text-muted);
}

.pl-city-count {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  backdrop-filter: blur(4px);
}

.pl-city-info {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pl-city-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--no-text-primary);
}

.pl-city-sub {
  font-size: 11px;
  color: var(--no-text-secondary);
}

/* ── Photo grid ──────────────────────────────────────────────────── */
.pl-photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 6px;
}

.pl-photo-item {
  position: relative;
  aspect-ratio: 1;
  background: var(--no-bg-elevated);
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.2s;
  }

  &:hover img { transform: scale(1.04); }
}

.pl-photo-item--empty {
  width: 100%;
  height: 100%;
  background: var(--no-bg-elevated);
}

.pl-photo-date {
  position: absolute;
  bottom: 6px;
  left: 6px;
  background: rgba(0,0,0,0.5);
  color: #fff;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 6px;
  backdrop-filter: blur(3px);
  pointer-events: none;
}

.pl-load-more {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

/* ── States ──────────────────────────────────────────────────────── */
.pl-loading { padding: 40px 0; }
.pl-empty { display: flex; justify-content: center; padding: 60px 0; }

/* ── Mobile (H5) ─────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .pl-root { padding: 0 12px 32px; }

  .pl-header {
    flex-wrap: wrap;
    gap: 10px;
    padding: 14px 0 12px;
  }

  .pl-search { max-width: 100%; width: 100%; margin-left: 0; }

  .pl-city-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .pl-photo-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 3px;
  }

  .pl-title { font-size: 18px; }
}
</style>
