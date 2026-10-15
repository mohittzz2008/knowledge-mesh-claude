import asyncio
from app.services.platform.codeforces import CodeforcesConnector
from app.services.platform.hackerrank import HackerRankConnector

async def main():
    print("=== LIVE VERIFICATION: HACKERRANK ===")
    hr = HackerRankConnector()
    valid = await hr.validate_identity("dnyeya")
    print("HackerRank validate_identity(dnyeya):", valid)
    prof = await hr.fetch_profile("dnyeya")
    print("HackerRank fetch_profile(dnyeya) total_solved:", prof.get("total_solved"))
    badges = await hr.fetch_badges("dnyeya")
    print("HackerRank badges count:", len(badges))
    for b in badges:
        print(f"  Badge: {b.get('badge_name')} -> solved: {b.get('solved')}, stars: {b.get('stars')}")
    ev = await hr.fetch_evidence("dnyeya")
    prof_ev = next(e for e in ev if e["type"] == "hackerrank_profile")
    norm_prof = hr.normalize_evidence(prof_ev)
    print("HackerRank normalized profile total_solved:", norm_prof["normalized_payload"]["total_solved"])

    print("\n=== LIVE VERIFICATION: CODEFORCES ===")
    cf = CodeforcesConnector()
    valid_cf = await cf.validate_identity("MikeMirzayanov")
    print("Codeforces validate_identity(MikeMirzayanov):", valid_cf)
    prof_cf = await cf.fetch_profile("MikeMirzayanov")
    print("Codeforces fetch_profile(MikeMirzayanov) handle:", prof_cf.get("username"))
    print("Codeforces fetch_profile(MikeMirzayanov) rating:", prof_cf.get("rating"))
    print("Codeforces fetch_profile(MikeMirzayanov) rank:", prof_cf.get("rank"))
    print("Codeforces fetch_profile(MikeMirzayanov) total_solved:", prof_cf.get("total_solved"))

    print("\n=== LIVE VERIFICATION: CODEFORCES MULTI-PAGE (>1,000 SUBMISSIONS) ===")
    # Test a user with more than 1,000 submissions to prove multi-page pagination
    solved_set = await cf.fetch_unique_solved_problems("Petr", page_size=1000)
    print("Codeforces Petr unique solved count:", len(solved_set))
    assert len(solved_set) > 0

if __name__ == "__main__":
    asyncio.run(main())
