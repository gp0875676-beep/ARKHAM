# alerts/templates.py — message templates per alert type.
"""Static Markdown templates. Centralized so we never have raw strings scattered."""

WHALE_TRANSFER_TEMPLATE = (
    "🐋 *Whale Transfer*\n"
    "Chain: {chain}\n"
    "Wallet: `{wallet}`\n"
    "Direction: {direction}\n"
    "Token: {token}\n"
    "Amount: {amount}\n"
    "USD: ${usd}\n"
    "[Tx Link]({tx_url})\n"
)

EXCHANGE_FLOW_TEMPLATE = (
    "🏦 *Exchange Flow Detected*\n"
    "{base}\n"
    "Exchange: {exchange}\n"
    "Reason: {reason}\n"
)

CLUSTER_TEMPLATE = (
    "🔗 *Cluster Activity*\n"
    "{base}\n"
    "Cluster ID: {cluster_id} ({member_count} wallets)\n"
    "Members: `{members}`\n"
)

SCORED_ALERT_TEMPLATE = (
    "📊 *Significance Score: {score}/100{calibration_note}*\n"
    "_Reasoning: {explanation}_\n"
)
