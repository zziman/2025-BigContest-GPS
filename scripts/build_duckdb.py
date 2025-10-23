# scripts/build_duckdb.py
"""
CSV 파일들을 DuckDB로 변환하는 스크립트

공통 매핑 컬럼: 기준년월, 업종, 상권_지리

실행 방법:
    python scripts/build_duckdb.py

생성 결과:
    data/data.duckdb
"""
import duckdb
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from my_agent.utils.config import FRANCHISE_CSV, BIZ_AREA_CSV, DATA_DIR


def validate_csv_files():
    """CSV 파일 존재 여부 확인"""
    franchise_path = Path(FRANCHISE_CSV).expanduser()
    biz_area_path = Path(BIZ_AREA_CSV).expanduser()
    
    print("CSV 파일 확인 중...")
    
    if not franchise_path.exists():
        print(f"❌ 가맹점 CSV 파일을 찾을 수 없습니다: {franchise_path}")
        return False
    print(f"✓ 가맹점 CSV: {franchise_path}")
    
    if not biz_area_path.exists():
        print(f"❌ 상권 CSV 파일을 찾을 수 없습니다: {biz_area_path}")
        return False
    print(f"✓ 상권 CSV: {biz_area_path}")
    
    return True, franchise_path, biz_area_path


def build_database():
    """DuckDB 구축"""
    
    print("="*60)
    print("DuckDB 구축 시작")
    print("="*60)
    
    # 1. CSV 파일 확인
    validation_result = validate_csv_files()
    if not validation_result:
        sys.exit(1)
    
    _, franchise_path, biz_area_path = validation_result
    
    # 2. DB 파일 경로 설정
    db_path = Path(DATA_DIR) / "data.duckdb"
    
    # 기존 DB 파일 삭제 (재생성)
    if db_path.exists():
        print(f"\n⚠️  기존 DB 파일 삭제: {db_path}")
        db_path.unlink()
    
    # 3. DuckDB 연결
    print(f"\n🔧 DuckDB 생성 중: {db_path}")
    con = duckdb.connect(str(db_path))
    
    try:
        # 4. 가맹점 데이터 로드
        print("\n" + "─"*60)
        print("[1/2] franchise_data_addmetrics.csv 로딩...")
        print("─"*60)
        
        con.execute(f"""
            CREATE TABLE franchise AS 
            SELECT * FROM read_csv_auto(
                '{franchise_path}', 
                header=true, 
                delim=',',
                all_varchar=false,
                ignore_errors=false
            )
        """)
        
        franchise_count = con.execute("SELECT COUNT(*) FROM franchise").fetchone()[0]
        print(f"✅ {franchise_count:,} rows 로드 완료")
        
        # 컬럼 확인
        columns = con.execute("DESCRIBE franchise").fetchdf()
        print(f"   컬럼 수: {len(columns)}")
        print(f"   주요 컬럼: {', '.join(columns['column_name'].head(10).tolist())}...")
        
        # 5. 상권 데이터 로드
        print("\n" + "─"*60)
        print("[2/2] biz_area_addmetrics.csv 로딩...")
        print("─"*60)
        
        con.execute(f"""
            CREATE TABLE biz_area AS 
            SELECT * FROM read_csv_auto(
                '{biz_area_path}',
                header=true,
                delim=',',
                all_varchar=false,
                ignore_errors=false
            )
        """)
        
        biz_count = con.execute("SELECT COUNT(*) FROM biz_area").fetchone()[0]
        print(f"✅ {biz_count:,} rows 로드 완료")
        
        # 컬럼 확인
        columns = con.execute("DESCRIBE biz_area").fetchdf()
        print(f"   컬럼 수: {len(columns)}")
        print(f"   주요 컬럼: {', '.join(columns['column_name'].head(10).tolist())}...")
        
        # 6. 공통 매핑 컬럼 확인
        print("\n" + "─"*60)
        print("공통 매핑 컬럼 확인")
        print("─"*60)
        
        common_cols = ['기준년월', '업종', '상권_지리']
        
        franchise_cols = con.execute("DESCRIBE franchise").fetchdf()['column_name'].tolist()
        biz_cols = con.execute("DESCRIBE biz_area").fetchdf()['column_name'].tolist()
        
        print("\n[franchise 테이블]")
        for col in common_cols:
            exists = col in franchise_cols
            print(f"  {'✓' if exists else '✗'} {col}")
            if not exists:
                print(f"       필수 컬럼 누락!")
        
        print("\n[biz_area 테이블]")
        for col in common_cols:
            exists = col in biz_cols
            print(f"  {'✓' if exists else '✗'} {col}")
            if not exists:
                print(f"       필수 컬럼 누락!")
        
        # 7. 인덱스 생성
        print("\n" + "─"*60)
        print("인덱스 생성 중...")
        print("─"*60)
        
        # 가맹점 테이블 인덱스
        franchise_indexes = [
            ("idx_franchise_id", "가맹점_구분번호"),
            ("idx_franchise_date", "기준년월"),
            ("idx_franchise_name", "가맹점명"),
        ]
        
        for idx_name, column in franchise_indexes:
            try:
                con.execute(f"CREATE INDEX {idx_name} ON franchise({column})")
                print(f"✓ {idx_name}: franchise({column})")
            except Exception as e:
                print(f"⚠️  {idx_name} 생성 실패: {e}")
        
        # 복합 인덱스 (조회용)
        try:
            con.execute("CREATE INDEX idx_franchise_composite ON franchise(가맹점_구분번호, 기준년월)")
            print(f"✓ idx_franchise_composite: franchise(가맹점_구분번호, 기준년월)")
        except Exception as e:
            print(f"⚠️  복합 인덱스 생성 실패: {e}")
        
        # 조인용 복합 인덱스 (공통 컬럼)
        try:
            con.execute("CREATE INDEX idx_franchise_join ON franchise(기준년월, 상권_지리, 업종)")
            print(f"✓ idx_franchise_join: franchise(기준년월, 상권_지리, 업종)")
        except Exception as e:
            print(f"⚠️  조인 인덱스 생성 실패: {e}")
        
        # 상권 테이블 인덱스 (공통 컬럼 기반)
        try:
            con.execute("CREATE INDEX idx_biz_area_join ON biz_area(기준년월, 상권_지리, 업종)")
            print(f"✓ idx_biz_area_join: biz_area(기준년월, 상권_지리, 업종)")
        except Exception as e:
            print(f"⚠️  상권 조인 인덱스 생성 실패: {e}")
        
        # 8. 데이터 검증
        print("\n" + "="*60)
        print("데이터 검증")
        print("="*60)
        
        # 가맹점 테이블 검증
        print("\n[franchise 테이블]")
        print(f"  총 레코드 수: {franchise_count:,}")
        
        unique_stores = con.execute(
            "SELECT COUNT(DISTINCT 가맹점_구분번호) FROM franchise"
        ).fetchone()[0]
        print(f"  고유 가맹점 수: {unique_stores:,}")
        
        date_range = con.execute("""
            SELECT MIN(기준년월) as min_date, MAX(기준년월) as max_date 
            FROM franchise
        """).fetchone()
        print(f"  기준년월 범위: {date_range[0]} ~ {date_range[1]}")
        
        # 공통 컬럼 결측치 확인
        for col in common_cols:
            try:
                null_count = con.execute(f"""
                    SELECT COUNT(*) FROM franchise WHERE {col} IS NULL
                """).fetchone()[0]
                print(f"  {col} 결측치: {null_count:,} ({null_count/franchise_count*100:.1f}%)")
            except:
                pass
        
        # 샘플 데이터 확인
        sample = con.execute("""
            SELECT 가맹점_구분번호, 가맹점명, 기준년월, 업종, 상권_지리
            FROM franchise 
            LIMIT 3
        """).fetchdf()
        print(f"\n  샘플 데이터 (3행):")
        print(sample.to_string(index=False))
        
        # 상권 테이블 검증
        print("\n[biz_area 테이블]")
        print(f"  총 레코드 수: {biz_count:,}")
        
        # 공통 컬럼 결측치 확인
        for col in common_cols:
            try:
                null_count = con.execute(f"""
                    SELECT COUNT(*) FROM biz_area WHERE {col} IS NULL
                """).fetchone()[0]
                print(f"  {col} 결측치: {null_count:,} ({null_count/biz_count*100:.1f}%)")
            except:
                pass
        
        # 9. 조인 테스트 (공통 컬럼 확인)
        print("\n" + "="*60)
        print("조인 테스트 (공통 컬럼)")
        print("="*60)
        
        # 조인 가능한 레코드 수 확인
        join_test = con.execute("""
            SELECT COUNT(*) as join_count
            FROM franchise f
            INNER JOIN biz_area b 
                ON f.기준년월 = b.기준년월 
                AND f.상권_지리 = b.상권_지리 
                AND f.업종 = b.업종
        """).fetchone()[0]
        
        print(f"\n✓ 조인 가능한 franchise 레코드: {join_test:,} / {franchise_count:,}")
        print(f"  조인 성공률: {join_test/franchise_count*100:.1f}%")
        
        # 조인 안되는 케이스 분석
        unmatch = con.execute("""
            SELECT COUNT(*) as unmatch_count
            FROM franchise f
            LEFT JOIN biz_area b 
                ON f.기준년월 = b.기준년월 
                AND f.상권_지리 = b.상권_지리 
                AND f.업종 = b.업종
            WHERE b.기준년월 IS NULL
        """).fetchone()[0]
        
        if unmatch > 0:
            print(f"\n⚠️  조인 안되는 레코드: {unmatch:,}")
            print(f"  원인 분석 중...")
            
            # 원인 분석
            sample_unmatch = con.execute("""
                SELECT f.기준년월, f.업종, f.상권_지리, f.가맹점명
                FROM franchise f
                LEFT JOIN biz_area b 
                    ON f.기준년월 = b.기준년월 
                    AND f.상권_지리 = b.상권_지리 
                    AND f.업종 = b.업종
                WHERE b.기준년월 IS NULL
                LIMIT 5
            """).fetchdf()
            
            print("\n  조인 실패 샘플 (5건):")
            print(sample_unmatch.to_string(index=False))
        
        # 10. 성능 테스트
        print("\n" + "="*60)
        print("쿼리 성능 테스트")
        print("="*60)
        
        import time
        
        # 테스트 1: 가맹점 ID 검색
        print("\n[테스트 1] 가맹점 ID로 검색")
        test_id = con.execute(
            "SELECT 가맹점_구분번호 FROM franchise LIMIT 1"
        ).fetchone()[0]
        
        start = time.time()
        result = con.execute("""
            SELECT * FROM franchise 
            WHERE 가맹점_구분번호 = ?
        """, [test_id]).fetchdf()
        elapsed = time.time() - start
        
        print(f"  검색 가맹점: {test_id}")
        print(f"  결과: {len(result)} rows")
        print(f"  소요 시간: {elapsed*1000:.2f}ms")
        
        # 테스트 2: 가맹점명 검색
        print("\n[테스트 2] 가맹점명으로 검색 (LIKE)")
        start = time.time()
        result = con.execute("""
            SELECT * FROM franchise 
            WHERE 가맹점명 LIKE '%본죽%'
            LIMIT 10
        """).fetchdf()
        elapsed = time.time() - start
        
        print(f"  검색어: '본죽'")
        print(f"  결과: {len(result)} rows")
        print(f"  소요 시간: {elapsed*1000:.2f}ms")
        
        # 테스트 3: 조인 쿼리 (공통 컬럼)
        print("\n[테스트 3] 가맹점-상권 조인 (공통 컬럼)")
        start = time.time()
        result = con.execute("""
            SELECT 
                f.가맹점명, 
                f.업종, 
                f.상권_지리,
                b.당월_매출_금액,
                b.점포_수
            FROM franchise f
            LEFT JOIN biz_area b 
                ON f.기준년월 = b.기준년월 
                AND f.상권_지리 = b.상권_지리 
                AND f.업종 = b.업종
            LIMIT 100
        """).fetchdf()
        elapsed = time.time() - start
        
        print(f"  결과: {len(result)} rows")
        print(f"  조인 성공: {result['당월_매출_금액'].notna().sum()} rows")
        print(f"  소요 시간: {elapsed*1000:.2f}ms")
        
        # 11. 완료
        con.close()
        
        print("\n" + "="*60)
        print("✅ DuckDB 구축 완료!")
        print("="*60)
        print(f"저장 위치: {db_path.absolute()}")
        print(f"파일 크기: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
        print("\n매핑 정보:")
        print("  공통 컬럼: 기준년월, 업종, 상권_지리")
        print(f"  조인 성공률: {join_test/franchise_count*100:.1f}%")
        print("\n다음 단계:")
        print("  1. config.py에서 USE_DUCKDB = True로 변경")
        print("  2. mcp/tools.py 코드 수정")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        con.close()
        sys.exit(1)


if __name__ == "__main__":
    build_database()