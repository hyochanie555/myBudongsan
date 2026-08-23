# 🏙️ 부동산 매물 스크래퍼 & 모바일 뷰 설정 가이드

GitHub Actions 서버에서 정해진 시간에 자동으로 스크래핑을 수행하고 GitHub Pages 대시보드를 갱신합니다. (로컬 컴퓨터에서도 직접 실행 가능)

---

## 1. ⚙️ GitHub Actions 자동 실행 (서버 자동화)

GitHub Actions 워크플로([.github/workflows/scrape_real_estate.yml](file:///D:/2.%EA%B0%9C%EB%B0%9C/Git/myBudongsan/.github/workflows/scrape_real_estate.yml))가 **하루 6회(한국 시간 기준 05:10, 09:10, 11:10, 15:10, 18:10, 21:10)** 자동으로 실행됩니다.

- **스케줄 주기 (KST 기준, 정각 대기열 부하 방지를 위해 10분 설정)**:
  - 05:10 (오전 5시 10분)
  - 09:10 (오전 9시 10분)
  - 11:10 (오전 11시 10분)
  - 15:10 (오후 3시 10분)
  - 18:10 (오후 6시 10분)
  - 21:10 (오후 9시 10분)
- **수동 즉시 실행**:
  - GitHub 저장소 > **Actions** 탭 > **Scrape Real Estate Listings** 워크플로 선택 > **Run workflow** 클릭

---

## 2. 🖥️ 로컬 수동 실행 및 확인

내 컴퓨터에서 직접 스크래핑하여 결과를 GitHub에 올리려면:

```powershell
./sync_listings.ps1
# 또는 실행_budongsan.bat 실행
```

---

## 3. 📱 모바일에서 확인하기

1. 본인의 **GitHub Pages URL**을 스마트폰 홈 화면이나 브라우저에 북마크해 두세요.
2. 하루 6번 자동으로 최신 매물 현황과 변동 사항(신규 매물, 재등록, 거래 완료/만료, 시세 변동)이 업데이트됩니다.

