import { DomainRulesEditor } from "@/components/control/domain-rules-editor";
import type { DomainRule } from "@/types/control";

export function GlobalRulesManager({ rules }: { rules: DomainRule[] }) {
  return (
    <DomainRulesEditor
      scopeType="global"
      scopeId={null}
      title="Network-wide website rules"
      description="Block or allow a DNS domain for every private-network client that actually uses the configured Technitium DNS server. HTTPS content remains encrypted."
      reason="Administrator network-wide rule"
      emptyMessage="No network-wide website rules."
      initialRules={rules}
    />
  );
}
