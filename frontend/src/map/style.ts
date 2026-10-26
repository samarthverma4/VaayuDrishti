import type { StyleSpecification } from '@maplibre/maplibre-gl-style-spec'

// Offline cartographic style built only from VYOMTRA's own boundary files (no tile server).
const GEO = '/api/v1/assets/geo'

function graticule(step = 5): GeoJSON.FeatureCollection {
  const f: GeoJSON.Feature[] = []
  for (let lon = 25; lon <= 135; lon += step)
    f.push({ type: 'Feature', properties: { kind: 'meridian', v: lon }, geometry: { type: 'LineString', coordinates: [[lon, -25], [lon, 55]] } })
  for (let lat = -25; lat <= 55; lat += step)
    f.push({ type: 'Feature', properties: { kind: 'parallel', v: lat }, geometry: { type: 'LineString', coordinates: [[25, lat], [135, lat]] } })
  return { type: 'FeatureCollection', features: f }
}

const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }
export const EMPTY = empty

export const COLORS = {
  ion: '#66DCE7',
  teal: '#39BCA7',
  ink: '#F2F5F4',
  muted: '#94A8B6',
  line: '#314554',
  amber: '#F3B85C',
  coral: '#EF6B61',
  magenta: '#D85797',
  blue: '#397FE8',
  compareA: '#F3B85C',
  compareB: '#66DCE7',
}

export function baseStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      countries: { type: 'geojson', data: `${GEO}/countries.geojson`, attribution: 'Natural Earth (India POV) · geoBoundaries (LGD, ODbL) · ECMWF ENS CC BY 4.0 · IBTrACS' },
      states: { type: 'geojson', data: `${GEO}/states.geojson` },
      districts: { type: 'geojson', data: `${GEO}/districts.geojson`, promoteId: 'id' },
      coast: { type: 'geojson', data: `${GEO}/coastline.geojson` },
      graticule: { type: 'geojson', data: graticule() },
      field: { type: 'image', url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', coordinates: [[0, 1], [1, 1], [1, 0], [0, 0]] },
      isobars: { type: 'geojson', data: empty },
      envelope: { type: 'geojson', data: empty },
      members: { type: 'geojson', data: empty, promoteId: 'member' },
      memberPos: { type: 'geojson', data: empty },
      mean: { type: 'geojson', data: empty },
      meanPos: { type: 'geojson', data: empty },
      best: { type: 'geojson', data: empty },
      bestPos: { type: 'geojson', data: empty },
      landfall: { type: 'geojson', data: empty },
      overview: { type: 'geojson', data: empty, promoteId: 'id' },
      verifyLinks: { type: 'geojson', data: empty },
      snapshot: { type: 'geojson', data: empty },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#080F1C' } },
      { id: 'grat', type: 'line', source: 'graticule', paint: { 'line-color': '#16283a', 'line-width': 0.6 } },
      { id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': ['case', ['==', ['get', 'iso3'], 'IND'], '#13263a', '#0f1d2c'] } },
      { id: 'field', type: 'raster', source: 'field', paint: { 'raster-opacity': 0.82, 'raster-fade-duration': 0, 'raster-resampling': 'linear' } },
      { id: 'districts-hit', type: 'fill', source: 'districts', paint: { 'fill-color': '#000', 'fill-opacity': 0 } },
      { id: 'districts-line', type: 'line', source: 'districts', minzoom: 4.6, paint: { 'line-color': '#26394a', 'line-width': 0.5 } },
      { id: 'district-sel-fill', type: 'fill', source: 'districts', filter: ['==', ['get', 'id'], ''], paint: { 'fill-color': COLORS.ion, 'fill-opacity': 0.12 } },
      { id: 'district-sel', type: 'line', source: 'districts', filter: ['==', ['get', 'id'], ''], paint: { 'line-color': COLORS.ion, 'line-width': 1.8 } },
      { id: 'states-line', type: 'line', source: 'states', paint: { 'line-color': '#2c4255', 'line-width': 0.7 } },
      { id: 'countries-line', type: 'line', source: 'countries', paint: { 'line-color': '#3b5468', 'line-width': 0.9 } },
      { id: 'coast', type: 'line', source: 'coast', paint: { 'line-color': '#4f6b80', 'line-width': 0.9 } },
      { id: 'isobars', type: 'line', source: 'isobars', paint: { 'line-color': 'rgba(242,245,244,0.22)', 'line-width': ['case', ['==', ['%', ['get', 'hpa'], 4], 0], 1.0, 0.5] } },
      { id: 'overview-line', type: 'line', source: 'overview', paint: { 'line-color': ['case', ['boolean', ['feature-state', 'hover'], false], COLORS.ion, COLORS.muted], 'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 2.4, 1.3], 'line-opacity': 0.85 } },
      { id: 'overview-hit', type: 'line', source: 'overview', paint: { 'line-color': '#000', 'line-width': 14, 'line-opacity': 0 } },
      { id: 'envelope-fill', type: 'fill', source: 'envelope', paint: { 'fill-color': COLORS.ion, 'fill-opacity': 0.07 } },
      { id: 'envelope-line', type: 'line', source: 'envelope', paint: { 'line-color': COLORS.ion, 'line-opacity': 0.55, 'line-width': 1, 'line-dasharray': [3, 3] } },
      { id: 'members', type: 'line', source: 'members', paint: {
        'line-color': ['case', ['boolean', ['feature-state', 'selected'], false], COLORS.ion, ['boolean', ['feature-state', 'hover'], false], COLORS.ink, '#9fb3c2'],
        'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, ['boolean', ['feature-state', 'hover'], false], 0.95, 0.32],
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2.2, ['boolean', ['feature-state', 'hover'], false], 1.8, 0.8],
      } },
      { id: 'members-hit', type: 'line', source: 'members', paint: { 'line-color': '#000', 'line-width': 8, 'line-opacity': 0 } },
      { id: 'best', type: 'line', source: 'best', paint: { 'line-color': COLORS.ink, 'line-width': 1.6, 'line-dasharray': [2, 1.5], 'line-opacity': 0.9 } },
      { id: 'best-fix', type: 'circle', source: 'best', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 1.8, 'circle-color': COLORS.ink } },
      { id: 'mean', type: 'line', source: 'mean', paint: { 'line-color': COLORS.teal, 'line-width': 2.6 } },
      { id: 'verify-links', type: 'line', source: 'verifyLinks', paint: { 'line-color': COLORS.coral, 'line-width': ['case', ['boolean', ['get', 'active'], false], 2.5, 1], 'line-opacity': ['case', ['boolean', ['get', 'active'], false], 1, 0.5] } },
      { id: 'member-pos', type: 'circle', source: 'memberPos', paint: { 'circle-radius': 2.4, 'circle-color': '#c9d6df', 'circle-opacity': 0.75 } },
      { id: 'landfall', type: 'circle', source: 'landfall', paint: {
        'circle-radius': ['match', ['get', 'kind'], 'member', 2.5, 6],
        'circle-color': ['match', ['get', 'kind'], 'observed', COLORS.ink, 'member', COLORS.amber, COLORS.teal],
        'circle-opacity': ['match', ['get', 'kind'], 'member', 0.7, 1],
        'circle-stroke-color': '#080F1C', 'circle-stroke-width': ['match', ['get', 'kind'], 'member', 0, 2],
      } },
      { id: 'best-pos', type: 'circle', source: 'bestPos', paint: { 'circle-radius': 6, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': COLORS.ink, 'circle-stroke-width': 2 } },
      { id: 'snapshot-min', type: 'circle', source: 'snapshot', paint: { 'circle-radius': 7, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': COLORS.teal, 'circle-stroke-width': 2.5 } },
      { id: 'mean-pos-halo', type: 'circle', source: 'meanPos', paint: { 'circle-radius': 13, 'circle-color': COLORS.teal, 'circle-opacity': 0.18 } },
      { id: 'mean-pos', type: 'circle', source: 'meanPos', paint: { 'circle-radius': 5.5, 'circle-color': COLORS.teal, 'circle-stroke-color': '#080F1C', 'circle-stroke-width': 2 } },
    ],
  }
}
