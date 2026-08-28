import logging
from crawler.parsers.prefecture_template_loader import PrefectureTemplateLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """
    都道府県テンプレートから個別コンフィグファイルを一括生成する。
    """
    loader = PrefectureTemplateLoader()
    logger.info("Starting generation of prefecture configs from template...")
    loader.generate_all_configs()
    logger.info("All prefecture configs have been generated successfully.")

if __name__ == "__main__":
    main()
