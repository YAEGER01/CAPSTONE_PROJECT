from django.db.models import Q, Sum, Count, Prefetch
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.contrib.contenttypes.models import ContentType

from datetime import date

from core_system.guards import require_role
from core_system.models import (
    Department, Member, MonthlyDues, MembershipFee, MedicalAid, DeathAid,
    AidTrackingPost, Contribution, FundTransaction, SupportingProof,
    TransactionVerification,
)
from core_system.shared_view_utils import resolve_officer_from_session


@never_cache
def hx_finance_collections_module(request: HttpRequest):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    officer = resolve_officer_from_session(request)
    officer_role = (request.session.get("role") or "treasurer").strip().lower()

    context = {
        "officer_full_name": officer.full_name if officer else officer_role,
        "officer_role": officer_role,
    }

    return render(request, "htmx/finance_collections.html", context)


@require_GET
def fc_department_list(request: HttpRequest):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    result = []
    for d in Department.objects.order_by("name"):
        text_member_count = Member.objects.filter(department=d.name).count()
        text_active_count = Member.objects.filter(department=d.name, membership_status__in=["Active", "Permanent", "Temporary"]).count()
        result.append({
            "id": d.department_id_PK,
            "name": d.name,
            "member_count": text_member_count,
            "active_count": text_active_count,
        })

    return JsonResponse({
        "ok": True,
        "departments": result,
    })


@require_GET
def fc_department_summary(request: HttpRequest, dept_id: int):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    dept = get_object_or_404(Department, department_id_PK=dept_id)
    members = list(Member.objects.filter(
        Q(department_id_FK=dept_id) | Q(department=dept.name)
    ).order_by("full_name"))
    member_ids = [m.member_id_PK for m in members]
    member_map = {m.member_id_PK: m for m in members}

    current_year = "2026"
    verified_statuses = ["Auditor Verified", "Approved"]

    tvs = list(TransactionVerification.objects.filter(
        table_name__in=["monthly_dues", "medical_aid", "death_aid"],
        verification_status__in=verified_statuses,
    ))

    md_ids = [tv.record_id for tv in tvs if tv.table_name == "monthly_dues"]
    med_ids = [tv.record_id for tv in tvs if tv.table_name == "medical_aid"]
    dth_ids = [tv.record_id for tv in tvs if tv.table_name == "death_aid"]

    all_dues = list(MonthlyDues.objects.filter(
        dues_id_PK__in=md_ids,
        member_id_FK__in=member_ids,
    ).select_related("member_id_FK"))
    all_medical = list(MedicalAid.objects.filter(
        medical_aid_id_PK__in=med_ids,
        member_id_FK__in=member_ids,
    ).select_related("member_id_FK"))
    all_death = list(DeathAid.objects.filter(
        death_aid_id_PK__in=dth_ids,
        member_id_FK__in=member_ids,
    ).select_related("member_id_FK"))

    dues_by_member = {}
    for d in all_dues:
        mid = d.member_id_FK_id
        dues_by_member.setdefault(mid, []).append(d)

    medical_by_member = {}
    for a in all_medical:
        mid = a.member_id_FK_id
        medical_by_member.setdefault(mid, []).append(a)

    death_by_member = {}
    for a in all_death:
        mid = a.member_id_FK_id
        death_by_member.setdefault(mid, []).append(a)

    active_posts = list(AidTrackingPost.objects.filter(
        is_active=True, status="tracking",
    ).prefetch_related(
        Prefetch("contributions", queryset=Contribution.objects.filter(member_id_FK__in=member_ids), to_attr="member_contributions"),
    ))

    contrib_by_member = {}
    for post in active_posts:
        for c in getattr(post, "member_contributions", []):
            mid = c.member_id_FK_id
            contrib_by_member.setdefault(mid, []).append(c)

    result_members = []
    for m in members:
        mid = m.member_id_PK

        member_dues = dues_by_member.get(mid, [])
        current_dues = [d for d in member_dues if d.month_covered.startswith(current_year)]
        paid_count = sum(1 for d in current_dues if d.payment_status in verified_statuses)

        member_contribs = contrib_by_member.get(mid, [])
        contrib_posts = [
            {
                "post_id": c.aid_tracking_post_id_FK.post_id_PK if c.aid_tracking_post_id_FK else None,
                "aid_type": c.aid_tracking_post_id_FK.aid_type if c.aid_tracking_post_id_FK else "",
                "status": c.status,
                "expected": float(c.expected_amount),
                "paid": float(c.paid_amount),
                "payment_status": c.status,
            }
            for c in member_contribs
        ]

        medical_list = medical_by_member.get(mid, [])[:10]
        death_list = death_by_member.get(mid, [])[:10]

        result_members.append({
            "member_id": mid,
            "full_name": m.full_name,
            "employee_id": m.employee_id or "",
            "position": m.position or "",
            "dues": {
                "current_year": {
                    "paid": paid_count,
                    "missed": max(0, len(current_dues) - paid_count),
                    "total_months": 12,
                },
                "year": int(current_year),
            },
            "contributions": {
                "total_expected": sum(c["expected"] for c in contrib_posts),
                "total_paid": sum(c["paid"] for c in contrib_posts),
                "posts": contrib_posts,
            },
            "claims": {
                "medical": [
                    {"id": a.medical_aid_id_PK, "status": a.status, "amount": float(a.validated_aid_amount or 0)}
                    for a in medical_list
                ],
                "death": [
                    {"id": a.death_aid_id_PK, "status": a.status, "amount": float(a.benefit_amount or 0)}
                    for a in death_list
                ],
            },
        })

    return JsonResponse({
        "ok": True,
        "department": {"id": dept.department_id_PK, "name": dept.name},
        "members": result_members,
    })


@require_GET
def fc_member_collections(request: HttpRequest, member_id: int):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    member = get_object_or_404(Member, member_id_PK=member_id)
    verified_statuses = ["Auditor Verified", "Approved"]

    year_param = request.GET.get("year")
    available_years = sorted(
        MonthlyDues.objects.filter(member_id_FK=member)
        .values_list("month_covered", flat=True)
        .distinct(),
        reverse=True,
    )
    available_years = sorted(set(int(y[:4]) for y in available_years if len(y) >= 4), reverse=True)
    today = date.today()
    if today.year not in available_years:
        available_years.append(today.year)
    available_years = sorted(available_years, reverse=True)

    target_year = int(year_param) if year_param else (available_years[0] if available_years else today.year)

    dues_grid = {}
    sy = str(target_year)
    tv_ids = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status__in=verified_statuses,
        record_id__in=MonthlyDues.objects.filter(
            member_id_FK=member, month_covered__startswith=sy
        ).values("dues_id_PK"),
    ).values_list("record_id", flat=True)
    dues = MonthlyDues.objects.filter(
        dues_id_PK__in=list(tv_ids),
        member_id_FK=member,
        month_covered__startswith=sy,
    ).order_by("month_covered")
    months = {}
    for m_range in range(1, 13):
        key = f"{target_year}-{m_range:02d}"
        record = dues.filter(month_covered=key).first()
        months[key] = {
            "status": record.payment_status if record else "NONE",
            "amount": float(record.amount) if record and record.amount else 0,
            "payment_method": record.payment_method if record else "",
        }
    dues_grid[target_year] = months

    contributions = Contribution.objects.filter(
        member_id_FK=member,
    ).select_related("aid_tracking_post_id_FK").order_by("-updated_at")[:50]

    contrib_list = []
    for c in contributions:
        contrib_list.append({
            "contribution_id": c.contribution_id_PK,
            "post_id": c.aid_tracking_post_id_FK.post_id_PK if c.aid_tracking_post_id_FK else None,
            "aid_type": c.aid_tracking_post_id_FK.aid_type if c.aid_tracking_post_id_FK else "",
            "expected": float(c.expected_amount),
            "paid": float(c.paid_amount),
            "status": c.status,
            "payment_date": str(c.payment_date) if c.payment_date else "",
        })

    medical_tv_ids = TransactionVerification.objects.filter(
        table_name="medical_aid",
        verification_status__in=verified_statuses,
    ).values_list("record_id", flat=True)
    medical_claims = list(MedicalAid.objects.filter(
        medical_aid_id_PK__in=list(medical_tv_ids),
        member_id_FK=member,
    ).order_by("-request_date").values(
        "medical_aid_id_PK", "status", "validated_aid_amount", "hospital_name", "request_date",
    )[:20])

    death_tv_ids = TransactionVerification.objects.filter(
        table_name="death_aid",
        verification_status__in=verified_statuses,
    ).values_list("record_id", flat=True)
    death_claims = list(DeathAid.objects.filter(
        death_aid_id_PK__in=list(death_tv_ids),
        member_id_FK=member,
    ).order_by("-claim_date").values(
        "death_aid_id_PK", "status", "benefit_amount", "deceased_name", "claim_date",
    )[:20])

    payment_history = []

    membership_tv_ids = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status__in=verified_statuses,
    ).values_list("record_id", flat=True)
    membership_tv_map = {
        tv.record_id: tv.verification_status
        for tv in TransactionVerification.objects.filter(table_name="membership_fee", record_id__in=list(membership_tv_ids))
    }
    for fee in MembershipFee.objects.filter(
        member_id_FK=member,
        fee_id_PK__in=list(membership_tv_ids),
    ).order_by("-payment_date")[:30]:
        payment_history.append({
            "type": "membership_fee",
            "category": "Membership Fee",
            "date": str(fee.payment_date) if fee.payment_date else "",
            "amount": float(fee.amount),
            "description": f"Membership fee — {fee.payment_method or ''}",
            "status": membership_tv_map.get(fee.fee_id_PK, fee.payment_status or ""),
        })

    monthly_tv_ids = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status__in=verified_statuses,
    ).values_list("record_id", flat=True)
    monthly_tv_map = {
        tv.record_id: tv.verification_status
        for tv in TransactionVerification.objects.filter(table_name="monthly_dues", record_id__in=list(monthly_tv_ids))
    }
    for md in MonthlyDues.objects.filter(
        member_id_FK=member,
        dues_id_PK__in=list(monthly_tv_ids),
    ).order_by("-payment_date")[:30]:
        payment_history.append({
            "type": "monthly_dues",
            "category": "Monthly Dues",
            "date": str(md.payment_date) if md.payment_date else "",
            "amount": float(md.amount),
            "description": f"Dues — {md.month_covered or ''}",
            "status": monthly_tv_map.get(md.dues_id_PK, md.payment_status or ""),
        })

    contrib_ids = [c.contribution_id_PK for c in contributions]
    contrib_tv_map = {
        tv.record_id: tv.verification_status
        for tv in TransactionVerification.objects.filter(table_name="contribution", record_id__in=contrib_ids)
    }
    for c in contributions:
        if c.paid_amount == 0 and c.status == "NOT_PAID":
            continue
        payment_history.append({
            "type": "aid",
            "category": "Aids",
            "date": str(c.payment_date) if c.payment_date else "",
            "amount": float(c.paid_amount),
            "description": f"{c.aid_tracking_post_id_FK.aid_type if c.aid_tracking_post_id_FK else 'Contribution'}",
            "status": contrib_tv_map.get(c.contribution_id_PK, c.status),
        })

    medical_ids = [c["medical_aid_id_PK"] for c in medical_claims]
    medical_tv_map = {
        tv.record_id: tv.verification_status
        for tv in TransactionVerification.objects.filter(table_name="medical_aid", record_id__in=medical_ids)
    }
    for c in medical_claims:
        payment_history.append({
            "type": "claim",
            "category": "Claims",
            "date": str(c["request_date"]) if c["request_date"] else "",
            "amount": float(c["validated_aid_amount"] or 0),
            "description": f"Medical aid — {c['hospital_name'] or ''}",
            "status": medical_tv_map.get(c["medical_aid_id_PK"], c["status"]),
        })

    death_ids = [d["death_aid_id_PK"] for d in death_claims]
    death_tv_map = {
        tv.record_id: tv.verification_status
        for tv in TransactionVerification.objects.filter(table_name="death_aid", record_id__in=death_ids)
    }
    for d in death_claims:
        payment_history.append({
            "type": "claim",
            "category": "Claims",
            "date": str(d["claim_date"]) if d["claim_date"] else "",
            "amount": float(d["benefit_amount"] or 0),
            "description": f"Death aid — {d['deceased_name'] or ''}",
            "status": death_tv_map.get(d["death_aid_id_PK"], d["status"]),
        })

    payment_history.sort(key=lambda x: x["date"], reverse=True)

    return JsonResponse({
        "ok": True,
        "selected_year": target_year,
        "available_years": available_years,
        "member": {
            "member_id": member.member_id_PK,
            "full_name": member.full_name,
            "employee_id": member.employee_id or "",
            "department": member.department or "",
            "position": member.position or "",
            "membership_status": member.membership_status or "",
        },
        "dues_grid": dues_grid,
        "contributions": contrib_list,
        "payment_history": payment_history,
        "claims": {
            "medical": [
                {
                    "id": c["medical_aid_id_PK"],
                    "status": c["status"],
                    "amount": float(c["validated_aid_amount"] or 0),
                    "hospital": c["hospital_name"],
                    "date": str(c["request_date"]) if c["request_date"] else "",
                }
                for c in medical_claims
            ],
            "death": [
                {
                    "id": d["death_aid_id_PK"],
                    "status": d["status"],
                    "amount": float(d["benefit_amount"] or 0),
                    "deceased": d["deceased_name"],
                    "date": str(d["claim_date"]) if d["claim_date"] else "",
                }
                for d in death_claims
            ],
        },
    })


@require_GET
def fc_fund_activity(request: HttpRequest):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    page = int(request.GET.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page

    transactions = FundTransaction.objects.select_related(
        "recorded_by_user_id_FK",
    ).order_by("-recorded_at")[offset:offset + per_page]

    total = FundTransaction.objects.count()
    total_pages = (total + per_page - 1) // per_page

    proof_ct = ContentType.objects.get_for_model(FundTransaction)
    tx_ids = [t.transaction_id_PK for t in transactions]
    proofs_map = {}
    if tx_ids:
        proofs_qs = SupportingProof.objects.filter(
            content_type=proof_ct,
            object_id__in=tx_ids,
        ).values("object_id", "proof_id_PK", "file_name")
        for p in proofs_qs:
            oid = p["object_id"]
            proofs_map.setdefault(oid, []).append({
                "id": p["proof_id_PK"],
                "file_url": f"/api/fund-ledger/proof/{p['proof_id_PK']}/file/",
                "file_name": p["file_name"],
            })

    items = []
    for t in transactions:
        items.append({
            "transaction_id": t.transaction_id_PK,
            "direction": t.direction,
            "amount": float(t.amount),
            "source_type": t.source_type,
            "source_id": t.source_id,
            "description": t.description,
            "reference_number": t.reference_number or "",
            "recorded_by": t.recorded_by_user_id_FK.full_name if t.recorded_by_user_id_FK else "",
            "recorded_at": t.recorded_at.isoformat() if t.recorded_at else "",
            "proofs": proofs_map.get(t.transaction_id_PK, []),
        })

    return JsonResponse({
        "ok": True,
        "transactions": items,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


def _resolve_actual_payout(source_type: str, source_id: int):
    """Trace AidTrackingPost -> FundTransaction to find the actual disbursed amount."""
    post = AidTrackingPost.objects.filter(
        source_type=source_type, source_id=source_id
    ).first()
    if post:
        txns = FundTransaction.objects.filter(
            source_type="aid_post_payment",
            source_id=post.post_id_PK,
            direction="outflow",
        )
    else:
        txns = FundTransaction.objects.filter(
            source_type=source_type,
            source_id=source_id,
            direction="outflow",
        )
    total = sum(t.amount for t in txns)
    return total, list(txns)


@require_GET
def fc_medical_aid_detail(request: HttpRequest, claim_id: int):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard
    try:
        aid = MedicalAid.objects.select_related("member_id_FK").get(medical_aid_id_PK=claim_id)
    except MedicalAid.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Medical aid not found."}, status=404)

    total_paid, txns = _resolve_actual_payout("medical_aid", claim_id)
    payment_status = "Disbursed" if total_paid > 0 else ("Approved — Awaiting Disbursement" if aid.president_decision == "Approved" else aid.status)

    return JsonResponse({
        "ok": True,
        "type": "medical",
        "claim": {
            "id": aid.medical_aid_id_PK,
            "member_name": aid.member_id_FK.full_name if aid.member_id_FK else "",
            "request_date": str(aid.request_date) if aid.request_date else "",
            "requested_amount": float(aid.requested_amount) if aid.requested_amount else 0,
            "hospital_name": aid.hospital_name or "",
            "hospital_date": str(aid.hospital_date) if aid.hospital_date else "",
            "reason": aid.reason or "",
            "hospital_bill_amount": float(aid.hospital_bill_amount) if aid.hospital_bill_amount else 0,
            "claim_year": aid.claim_year,
            "total_paid": total_paid,
            "status": aid.status,
            "payment_status": payment_status,
            "president_decision": aid.president_decision or "",
            "disbursement_source": aid.disbursement_source or "",
            "release_reference": aid.release_reference or "",
            "acknowledgement_reference": aid.acknowledgement_reference or "",
            "fund_transactions": [
                {
                    "id": t.transaction_id_PK,
                    "amount": float(t.amount),
                    "direction": t.direction,
                    "description": t.description,
                    "recorded_at": t.recorded_at.isoformat() if t.recorded_at else "",
                }
                for t in txns
            ],
        },
    })


@require_GET
def fc_death_aid_detail(request: HttpRequest, claim_id: int):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard
    try:
        aid = DeathAid.objects.select_related("member_id_FK", "claimant_id_FK").get(death_aid_id_PK=claim_id)
    except DeathAid.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Death aid not found."}, status=404)

    total_paid, txns = _resolve_actual_payout("death_aid", claim_id)
    payment_status = "Disbursed" if total_paid > 0 else ("Approved — Awaiting Disbursement" if aid.president_decision == "Approved" else aid.status)

    return JsonResponse({
        "ok": True,
        "type": "death",
        "claim": {
            "id": aid.death_aid_id_PK,
            "member_name": aid.member_id_FK.full_name if aid.member_id_FK else "",
            "claim_date": str(aid.claim_date) if aid.claim_date else "",
            "claim_type": aid.claim_type or "",
            "deceased_name": aid.deceased_name or "",
            "relationship_to_member": aid.relationship_to_member or "",
            "funeral_location": aid.funeral_location or "",
            "interment_date": str(aid.interment_date) if aid.interment_date else "",
            "total_paid": total_paid,
            "bill_amount": float(aid.bill_amount) if aid.bill_amount else 0,
            "status": aid.status,
            "payment_status": payment_status,
            "president_decision": aid.president_decision or "",
            "disbursement_source": aid.disbursement_source or "",
            "release_reference": aid.release_reference or "",
            "acknowledgement_reference": aid.acknowledgement_reference or "",
            "fund_transactions": [
                {
                    "id": t.transaction_id_PK,
                    "amount": float(t.amount),
                    "direction": t.direction,
                    "description": t.description,
                    "recorded_at": t.recorded_at.isoformat() if t.recorded_at else "",
                }
                for t in txns
            ],
        },
    })


@require_GET
def fc_member_proofs(request: HttpRequest, member_id: int):
    guard = require_role(request, role=["treasurer", "auditor", "president"])
    if guard:
        return guard

    member = get_object_or_404(Member, member_id_PK=member_id)

    member_ct = ContentType.objects.get_for_model(Member)
    dues_ct = ContentType.objects.get_for_model(MonthlyDues)
    medical_ct = ContentType.objects.get_for_model(MedicalAid)
    death_ct = ContentType.objects.get_for_model(DeathAid)

    proofs = SupportingProof.objects.filter(
        Q(content_type=member_ct, object_id=member_id)
        | Q(
            content_type=dues_ct,
            object_id__in=MonthlyDues.objects.filter(
                member_id_FK=member
            ).values("dues_id_PK"),
        )
        | Q(
            content_type=medical_ct,
            object_id__in=MedicalAid.objects.filter(
                member_id_FK=member
            ).values("medical_aid_id_PK"),
        )
        | Q(
            content_type=death_ct,
            object_id__in=DeathAid.objects.filter(
                member_id_FK=member
            ).values("death_aid_id_PK"),
        )
    ).select_related("uploaded_by").order_by("-uploaded_at")[:100]

    return JsonResponse({
        "ok": True,
        "proofs": [
            {
                "id": p.proof_id_PK,
                "file_url": f"/api/fund-ledger/proof/{p.proof_id_PK}/file/",
                "file_name": p.file_name,
                "file_type": p.file_type,
                "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else "",
                "uploaded_by": p.uploaded_by.full_name if p.uploaded_by else "",
            }
            for p in proofs
        ],
    })
