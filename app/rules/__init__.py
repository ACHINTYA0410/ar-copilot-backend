from app.rules.po_validation import (
    CheckLinkedDealExistsRule, CheckAcademicYearCurrentRule, CheckAuthorizedCreatorRule,
    CheckFinanceApprovalAgingRule, CheckCustomerVerificationLinkRule, CheckNotificationRoutingRule,
)
from app.rules.document_content import (
    CheckSignaturesRule, CheckPanAttachedRule, CheckEffectiveDateRule,
    CheckStampDutyRule, CheckWitnessSignaturesRule, CheckCompanyLetterheadRule,
    CheckContractTermRule, CheckPageCompletenessRule,
)
from app.rules.hubspot_match import (
    MatchPanRule, MatchAmountRule, MatchCompanyNameRule,
    MatchGstRule, MatchContactDetailsRule, MatchAddressRule,
)
from app.rules.field_completeness import (
    CheckRequiredFieldsRule, CheckProductsConfiguredRule, CheckDealStageRule,
    CheckZoneApprovalRule, CheckOnboardingDateRule, CheckPaymentTermsRule,
)
from app.rules.policy import (
    CheckDeviationApprovalRule, CheckCreditLimitRule, CheckBlacklistRule,
    CheckRegulatoryComplianceRule, CheckTerritoryConflictRule, CheckSlaTermsRule,
)

ALL_RULES = [
    CheckSignaturesRule(), CheckPanAttachedRule(), CheckEffectiveDateRule(),
    CheckStampDutyRule(), CheckWitnessSignaturesRule(), CheckCompanyLetterheadRule(),
    CheckContractTermRule(), CheckPageCompletenessRule(),
    MatchPanRule(), MatchAmountRule(), MatchCompanyNameRule(),
    MatchGstRule(), MatchContactDetailsRule(), MatchAddressRule(),
    CheckRequiredFieldsRule(), CheckProductsConfiguredRule(), CheckDealStageRule(),
    CheckZoneApprovalRule(), CheckOnboardingDateRule(), CheckPaymentTermsRule(),
    CheckDeviationApprovalRule(), CheckCreditLimitRule(), CheckBlacklistRule(),
    CheckRegulatoryComplianceRule(), CheckTerritoryConflictRule(), CheckSlaTermsRule(),
    # PO validation rules
    CheckLinkedDealExistsRule(), CheckAcademicYearCurrentRule(), CheckAuthorizedCreatorRule(),
    CheckFinanceApprovalAgingRule(), CheckCustomerVerificationLinkRule(), CheckNotificationRoutingRule(),
]

RULE_REGISTRY = {rule.rule_id: rule for rule in ALL_RULES}
