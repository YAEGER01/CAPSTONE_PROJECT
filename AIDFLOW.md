# ISU-CAUFA — FMIS Aid Flow Specification

This document is the canonical, baseline business logic for Medical/Accidental-Sickness Aid and Death Aid contributions in the ISU-CAUFA FMIS. It is drawn directly from the ISU-CAUFA Constitution and By-Laws and adapted to the FMIS control flows (Treasurer → Auditor → President).

---

## 1. Medical / Accidental-Sickness Aid

Eligibility and amounts from the By-Laws:

- Hospital bill exceeding ₱20,000 (eligibility threshold)
- Contribution per contributing member: ₱100 (fixed)
- Aid can be requested once per calendar year per beneficiary
- Member must be in good standing to receive aid
- Retired members are exempt from paying the listed fees

System flow (FMIS):

1. Member requests aid (creates an Aid Case: MED-YYYY-NNNN)
2. Member uploads hospital bill and supporting documents
3. Treasurer validates:
   - Member status
   - Good standing
   - Hospital bill > ₱20,000
   - Once-a-year eligibility
4. Auditor verifies request and documents
5. President approves final request
6. FMIS creates an `Accidental/Sickness Aid Contribution` attached to the Aid Case
   - Contribution Required (per eligible member): ₱100
7. System sends contribution requests/notifications to eligible active members only
8. Treasurer records incoming contributions and tracks contributors
9. Auditor verifies recorded contributions against requests
10. President completes approval and authorizes release (if applicable)
11. Treasurer records the release/transfer and updates Fund Ledger & Case History

Important notes:

- The ₱20,000 value is an eligibility threshold for requesting aid, not the aid amount.
- The ₱100 is the contribution expected from each eligible member, collected once per case.
- The Aid Case should include: requester, case id, uploaded documents, eligibility checks, contributor list, total collected, additional source(s) for any shortfall, and release records.

---

## 2. Death Aid

By-Laws contribution amounts (per death aid case):

- Deceased member: ₱500
- Husband/Wife: ₱300
- Parent/Child: ₱250
- Full-blood Brother/Sister: ₱100

System flow (FMIS):

1. Member or authorized claimant submits Death Aid claim (creates Aid Case: DEA-YYYY-NNNN)
2. Upload required supporting documents (death certificate, proof of relationship, member status)
3. Treasurer validates:
   - Member status
   - Good standing
   - Relationship of deceased (map to contribution amount)
   - Required documents present
4. Auditor verifies claim and documents
5. President gives final approval
6. FMIS creates a `Death Aid Contribution` attached to the Aid Case and determines required contribution per eligible member
7. System sends contribution requests/notifications to eligible active members only
8. Treasurer records incoming contributions and tracks contributors
9. Auditor verifies recorded contributions
10. President completes approval; Treasurer processes release/recording
11. Fund Ledger & Case History updated

Important notes:

- Death benefits are received by the family only (per By-Laws).
- The system determines the expected amount per contributing member based on the deceased's relationship.

---

## 3. Single fix: target contribution notifications

Make the following explicit in the FMIS:

- Contribution notifications must be sent only to the members who are eligible to contribute for that Aid Case (do not treat aid contributions as generic monthly dues).
- Each Aid Case must carry an `expected_amount` attribute (e.g., ₱100 for medical, ₱500/₱300/₱250/₱100 for death cases) and a list of eligible contributors.
- Contributions are recorded against the Aid Case, not against the member's monthly due ledger.

---

## 4. Database / Financial concepts (separate models)

The FMIS must keep three separate financial concepts rather than a single generic payment record:

1. Monthly Due
   - Recurring: ₱50 (By-Laws monthly due)
2. Medical / Accidental-Sickness Contribution
   - Aid Case: MED-YYYY-NNNN
   - Contribution Required (per eligible member): ₱100
3. Death Aid Contribution
   - Aid Case: DEA-YYYY-NNNN
   - Contribution Required (per eligible member): ₱500 / ₱300 / ₱250 / ₱100

Recommended schema elements (high level):

- AidCase: id, case_type (MED/DEA), requester_member_id, created_at, status, expected_amount, eligibility_reason, documents (references), eligible_contributors (list or relation), total_collected, release_amount, shortfall_source
- ContributionRecord: id, aid_case_id (nullable), member_id, amount_expected, amount_paid, paid_at, recorded_by, status
- LedgerEntry: id, entry_type (monthly_due|aid_collection|aid_release), amount, source_account, dest_account, reference_id

---

## 5. Treasurer → Auditor → President control chain

Keep the Treasurer → Auditor → President approval chain in the FMIS as an internal control mechanism. Document clearly that this is the FMIS workflow for separation of duties; the By-Laws provide financial responsibilities but do not prescribe the exact digital approval steps.

---

## 6. Final flows (concise)

- Medical/Accidental-Sickness: Request → Treasurer Validation → Auditor Verification → President Approval → ₱100 Member Contribution → Treasurer Collection → Auditor Verification → President Completion → Treasurer Release/Recording → Ledger & History
- Death Aid: Claim → Treasurer Validation → Auditor Verification → President Approval → Determine ₱500/₱300/₱250/₱100 Contribution → Treasurer Collection → Auditor Verification → President Completion → Treasurer Release/Recording → Ledger & History

---

## 7. Eligibility rules summary

- Medical/Accidental-Sickness: hospital bill > ₱20,000; once per year; ₱100 contribution per eligible member; requester must be in good standing; retired exempt
- Death Aid: member ₱500; spouse ₱300; parent/child ₱250; full-blood sibling ₱100; requester/claimant must provide required documents; members must be in good standing; retired exempt

---

## 8. Medical Aid process notes (operational)

- The Medical Aid contribution is fixed at ₱100 per eligible contributor.
- The Treasurer collects the ₱100 contributions from eligible members and records contributors.
- Collection and distribution may be manual or digital; system records must reflect the reality (who contributed, how much, and source of any additional funds used to reach payout).
- Aid Case records should show: who requested, who contributed, total collected, source(s) of any additional funds, amount released, and audit trail for approvals.

---

If you want, I can next:

- Implement the recommended `AidCase` and `ContributionRecord` models in the codebase
- Add server-side validation for eligibility thresholds and relationship mapping
- Update the member dashboard to only notify eligible contributors
- Add unit tests to validate the flows

Please tell me which of the next steps you'd like me to implement first.
