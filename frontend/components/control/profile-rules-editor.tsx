import { DomainRulesEditor } from "@/components/control/domain-rules-editor";
import type { ControlProfile } from "@/types/control";

export function ProfileRulesEditor({ profile }: { profile: ControlProfile }) {
  return (
    <DomainRulesEditor
      scopeType="profile"
      scopeId={profile.id}
      title="Custom website rules"
      description="Rules match DNS domains, not encrypted page contents. An allow rule can also be temporary."
      reason={`${profile.name} profile custom rule`}
      emptyMessage="No custom website rules for this profile."
      initialRules={profile.domain_rules}
    />
  );
}
