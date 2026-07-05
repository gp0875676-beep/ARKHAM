# alerts/formatter.py — builds Markdown-safe alert messages.
"""Renders a TxEvent (+ context) into a Telegram-safe Markdown string.
Uses utils.markdown.escape_markdown on every dynamic field."""
from chains.base import TxEvent
from utils.markdown import escape_markdown
from alerts.templates import WHALE_TRANSFER_TEMPLATE, EXCHANGE_FLOW_TEMPLATE, CLUSTER_TEMPLATE, SCORED_ALERT_TEMPLATE


class AlertFormatter:
    def render(self, event: TxEvent, context=None, score=None) -> str:
        if context is None:
            context = {}
 
        wallet_label = event.from_address if event.direction == "out" else event.to_address
        usd_str = f"{event.usd_value:,.2f}" if event.usd_value else "N/A"
 
        base_msg = WHALE_TRANSFER_TEMPLATE.format(
            chain=escape_markdown(event.chain),
            wallet=escape_markdown(wallet_label),
            direction=escape_markdown(event.direction),
            token=escape_markdown(event.token_symbol),
            amount=escape_markdown(f"{event.amount_human:.4f}"),
            usd=escape_markdown(usd_str),
            tx_url=event.explorer_url
        )

        if context.get("exchange"):
            base_msg = EXCHANGE_FLOW_TEMPLATE.format(
                base=base_msg,
                exchange=escape_markdown(context["exchange"]),
                reason=escape_markdown(context["reason"])
            )

        if context.get("cluster_id"):
            members_str = ", ".join(context["cluster_members"][:3])
            if len(context["cluster_members"]) > 3:
                members_str += f" +{len(context['cluster_members']) - 3} more"
 
            base_msg = CLUSTER_TEMPLATE.format(
                base=base_msg,
                cluster_id=context["cluster_id"],
                member_count=context["cluster_count"],
                members=escape_markdown(members_str)
            )

        # Extract score object from context
        score_obj = context.get("score")
        if score_obj:
            base_msg = SCORED_ALERT_TEMPLATE.format(
                base=base_msg,
                score=score_obj.value,
                calibration_note=escape_markdown(getattr(score_obj, "calibration_note", "") or ""),
                explanation=escape_markdown(score_obj.explanation)
            )

        return base_msg
