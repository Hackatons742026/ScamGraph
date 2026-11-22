import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api, ApiRequestError, unwrap } from "@/api/client";
import type { CampaignDetail as CampaignDetailType } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LinksCard, MembersCard, RelatedGroupsCard, TimelineCard } from "@/features/campaigns/CampaignSections";
import { ExportLinks } from "@/features/campaigns/ExportLinks";
import { campaignHref, graphFocusHref } from "@/features/campaigns/links";
import { SplitDialog } from "@/features/overrides/SplitDialog";
import { formatDate, humanize } from "@/lib/domain";

function Summary({ campaign, onSplit }: { campaign: CampaignDetailType; onSplit: () => void }) {
  // Same cache entry as the Campaigns list: names the parent network and, for a network, its campaigns.
  const all = useQuery({ queryKey: ["campaigns"], queryFn: () => unwrap(api.GET("/api/campaigns")) });
  const network = campaign.network_id ? all.data?.find((c) => c.id === campaign.network_id) : undefined;
  const inNetwork = campaign.level === "network" ? (all.data ?? []).filter((c) => c.network_id === campaign.id) : [];
  const isCampaign = campaign.level === "campaign";
  const strongest = campaign.strongest_evidence;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">{campaign.label}</CardTitle>
            <Badge variant={isCampaign ? "danger" : "outline"}>{campaign.level}</Badge>
          </div>
          <p className="text-xs text-slate-500">
            {campaign.size} incident{campaign.size === 1 ? "" : "s"} · first seen {formatDate(campaign.first_seen)} · last seen{" "}
            {formatDate(campaign.last_seen)}
          </p>
          <p className="text-xs text-slate-500">
            {isCampaign
              ? "Campaign: incidents tied by strong shared evidence."
              : "Network: groups that share tooling or infrastructure, not necessarily one operator."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={graphFocusHref(campaign.id)}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            <Network className="h-3.5 w-3.5" aria-hidden />
            Open in graph
          </Link>
          {isCampaign && campaign.size >= 2 && (
            <Button type="button" size="sm" variant="outline" onClick={onSplit}>
              Split
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-500">Strongest evidence</span>
          {strongest ? (
            <>
              <TierBadge tier={strongest.tier} />
              <span className="text-xs text-slate-500">{humanize(strongest.type)}</span>
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{strongest.display}</code>
            </>
          ) : (
            <span className="text-xs text-slate-500">—</span>
          )}
        </div>
        {campaign.network_id && (
          <p className="text-xs text-slate-600">
            Part of a wider network:{" "}
            <Link to={campaignHref(campaign.network_id)} className="font-medium text-slate-900 underline-offset-2 hover:underline">
              {network?.label ?? "open network"}
            </Link>
          </p>
        )}
        {inNetwork.length > 0 && (
          <p className="text-xs text-slate-600">
            Campaigns in this network:{" "}
            {inNetwork.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link to={campaignHref(c.id)} className="font-medium text-slate-900 underline-offset-2 hover:underline">{c.label}</Link>
              </span>
            ))}
          </p>
        )}
        {isCampaign ? (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-500">Export</span>
            <ExportLinks campaignId={campaign.id} label={campaign.label} />
          </div>
        ) : (
          <p className="text-xs text-slate-400">Exports are per campaign; networks are not exported.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function CampaignDetail() {
  const { id = "" } = useParams();
  const [splitOpen, setSplitOpen] = useState(false);
  // Same key as SplitDialog, so opening Split reuses this response.
  const detail = useQuery({
    queryKey: ["campaigns", id],
    queryFn: () => unwrap(api.GET("/api/campaigns/{campaign_id}", { params: { path: { campaign_id: id } } })),
    enabled: !!id,
  });
  const notFound = detail.error instanceof ApiRequestError && detail.error.status === 404;
  const level = detail.data?.level === "network" ? "Network" : "Campaign";

  return (
    <>
      <PageHeader
        title={detail.data?.label ?? "Campaign detail"}
        description={detail.data ? `${level} · members, links, timeline and related groups` : undefined}
        actions={
          <Link to="/campaigns" className="text-sm text-slate-600 underline-offset-2 hover:underline">
            ← Back to campaigns
          </Link>
        }
      />
      {notFound ? (
        <p className="rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">
          Campaign not found. It may have been merged or split since the last run.{" "}
          <Link to="/campaigns" className="font-medium text-slate-800 underline underline-offset-2">Back to campaigns</Link>
        </p>
      ) : (
        <QueryState query={detail}>
          {(c) => (
            <div className="flex flex-col gap-4">
              <Summary campaign={c} onSplit={() => setSplitOpen(true)} />
              <MembersCard members={c.members} />
              <LinksCard campaign={c} />
              <RelatedGroupsCard id={c.id} />
              {c.timeline.length > 0 && <TimelineCard campaign={c} />}
            </div>
          )}
        </QueryState>
      )}
      {splitOpen && detail.data && <SplitDialog campaign={detail.data} onClose={() => setSplitOpen(false)} />}
    </>
  );
}
