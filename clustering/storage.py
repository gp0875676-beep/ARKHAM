# clustering/storage.py — cluster persistence helpers.
"""Thin caching wrapper around ClusterRepo to avoid repeat DB round-trips
for the same wallet/cluster lookups within a single scan cycle."""
from __future__ import annotations

from db.models import ClusterRepo
from utils.logger import get_logger

log = get_logger(__name__)


class ClusterStore:
    """In-memory cache layer over ClusterRepo. Cache is cycle-scoped:
    call `reset()` at the start of each scan cycle so stale entries never
    persist across cycles."""

    def __init__(self, repo: ClusterRepo | None = None) -> None:
        self.repo = repo or ClusterRepo()
        self._wallet_to_cluster: dict[tuple[str, str], int] = {}
        self._cluster_members: dict[int, list[str]] = {}

    def reset(self) -> None:
        self._wallet_to_cluster.clear()
        self._cluster_members.clear()

    async def get_or_create(self, chain: str, members: list[str]) -> int:
        """Return the cluster id for this group of wallets, creating one
        if none of them already belong to a cluster."""
        if not members:
            raise ValueError("get_or_create requires at least one wallet")

        cluster_id = await self.repo.assign_to_cluster(chain, members)
        for w in members:
            self._wallet_to_cluster[(chain, w)] = cluster_id
        self._cluster_members.pop(cluster_id, None)
        return cluster_id

    async def cluster_of(self, chain: str, wallet: str) -> int | None:
        key = (chain, wallet)
        if key in self._wallet_to_cluster:
            return self._wallet_to_cluster[key]
        cluster_id = await self.repo.get_cluster_by_wallet(chain, wallet)
        if cluster_id is not None:
            self._wallet_to_cluster[key] = cluster_id
        return cluster_id

    async def members_of(self, cluster_id: int) -> list[str]:
        if cluster_id in self._cluster_members:
            return self._cluster_members[cluster_id]
        members = await self.repo.get_members(cluster_id)
        self._cluster_members[cluster_id] = members
        return members
