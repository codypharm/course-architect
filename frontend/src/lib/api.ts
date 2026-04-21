import axios from 'axios'

// In production VITE_API_BASE_URL is the CloudFront domain (set at build time).
// In local dev it's unset, so requests go to /api/v1 (proxied by Vite).
const BASE_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : '/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})
