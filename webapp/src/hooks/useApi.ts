/**
 * React Query hooks for Nelson Freight API
 * Replaces raw fetch with cached, deduplicated queries
 *
 * Email hooks REMOVED 2026-04-17 — email send pipeline moved to
 * email_engine/web_server.py (local PC). See docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md
 */
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ── Health & Status ──────────────────────────────
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    staleTime: 60 * 1000,
  })
}

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: api.status,
    staleTime: 60 * 1000,
  })
}

// ── Tasks ────────────────────────────────────────
export function useTasks() {
  return useQuery({
    queryKey: ['tasks'],
    queryFn: api.tasks,
  })
}
