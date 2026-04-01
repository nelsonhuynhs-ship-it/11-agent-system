/**
 * React Query hooks for Nelson Freight API
 * Replaces raw fetch with cached, deduplicated queries
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, emailRateApi, campaignApi } from '@/lib/api'
import type {
  PreviewRequest,
  PreviewResponse,
  SendRequest,
  SendResponse,
  CampaignProspectsResponse,
  CampaignStats,
  CampaignPreviewRequest,
  CampaignSendRequest,
  CampaignSendResponse,
  CampaignBulkSendRequest,
  CampaignBulkSendResponse,
} from '@/lib/api'

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

// ── Email Rate ───────────────────────────────────
export function useCustomers() {
  return useQuery({
    queryKey: ['email-rate', 'customers'],
    queryFn: emailRateApi.customers,
    staleTime: 5 * 60 * 1000, // 5 min — customer list changes rarely
  })
}

export function useEmailConfig() {
  return useQuery({
    queryKey: ['email-rate', 'config'],
    queryFn: emailRateApi.config,
    staleTime: 10 * 60 * 1000,
  })
}

export function usePreview(req: PreviewRequest | null) {
  return useQuery({
    queryKey: ['email-rate', 'preview', req],
    queryFn: () => emailRateApi.preview(req!),
    enabled: !!req,
  })
}

export function useSendEmail() {
  const queryClient = useQueryClient()
  return useMutation<SendResponse, Error, SendRequest>({
    mutationFn: emailRateApi.send,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-rate'] })
      queryClient.invalidateQueries({ queryKey: ['campaign'] })
    },
  })
}

// ── Campaign ─────────────────────────────────────
export function useCampaignProspects(params: Parameters<typeof campaignApi.prospects>[0] = {}) {
  return useQuery<CampaignProspectsResponse>({
    queryKey: ['campaign', 'prospects', params],
    queryFn: () => campaignApi.prospects(params),
  })
}

export function useCampaignStats() {
  return useQuery<CampaignStats>({
    queryKey: ['campaign', 'stats'],
    queryFn: campaignApi.stats,
    staleTime: 60 * 1000,
  })
}

export function useCampaignPreview() {
  return useMutation<PreviewResponse & { template: string }, Error, CampaignPreviewRequest>({
    mutationFn: campaignApi.preview,
  })
}

export function useCampaignSend() {
  const queryClient = useQueryClient()
  return useMutation<CampaignSendResponse, Error, CampaignSendRequest>({
    mutationFn: campaignApi.send,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaign'] })
    },
  })
}

export function useCampaignBulkSend() {
  const queryClient = useQueryClient()
  return useMutation<CampaignBulkSendResponse, Error, CampaignBulkSendRequest>({
    mutationFn: campaignApi.bulkSend,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaign'] })
    },
  })
}
