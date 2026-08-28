"""
Update Qualification Grades
全省庁統一資格tags CSVを再読み込みしてDBを更新するスクリプト。
"""
import sys
sys.path.insert(0, ".")

from database.engine import get_session
from database.seeders.qualification_tag_seeder import seed_qualification_tags


def update_qualification_grades() -> dict:
    try:
        with get_session() as session:
            stats = seed_qualification_tags(session)
            print(f"Updated: {stats}")
            return stats
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    result = update_qualification_grades()
    print(f"Done: {result}")