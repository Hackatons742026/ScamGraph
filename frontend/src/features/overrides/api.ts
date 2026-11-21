import type { QueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { CampaignDetail, EdgeDecisionRequest, EdgeDecisionResponse, MergeRequest, SplitRequest } from "@/api/types";

export function postEdgeDecision(edgeId: string, body: EdgeDecisionRequest): Promise<EdgeDecisionResponse> {
  return unwrap(
    api.POST("/api/edges/{edge_id}/decision", {
      params: { path: { edge_id: edgeId } },
      body,
    }),
  );
}

export function mergeCampaigns(body: MergeRequest): Promise<CampaignDetail> {
  return unwrap(api.POST("/api/campaigns/merge", { body }));
}

export function splitCampaign(body: SplitRequest): Promise<CampaignDetail[]> {
  return unwrap(api.POST("/api/campaigns/split", { body }));
}

/** After an override, refresh the views that can change: graph, campaigns list, incidents. */
export function invalidateAfterOverride(client: QueryClient) {
  void client.invalidateQueries({ queryKey: ["graph"] });
  void client.invalidateQueries({ queryKey: ["campaigns"] });
  void client.invalidateQueries({ queryKey: ["incidents"] });
}
