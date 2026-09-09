"""Idempotent migration of owner-approved public facts (2026-09-09)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    path = ROOT / 'docs/rag/mastercheb.jsonl'
    chunks = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    updates = {
        'materials': (
            'В базовые тарифы входит первоначальная подготовка информации для базы знаний в любом формате объёмом примерно до тысячи страниц. Нужны актуальные услуги, цены, правила и примеры диалогов; особенности сложных материалов уточняем при согласовании. Какую информацию вы хотите передать помощнику?',
            'Base plans include initial preparation of knowledge-base information in any format, up to approximately one thousand pages. Please provide current services, prices, policies and dialogue examples; complex materials are reviewed when agreeing scope. What information would you like your assistant to use?',
            '基础方案包含首次整理任意格式、约一千页以内的知识库资料整理。请提供最新服务、价格、规则及对话示例，复杂资料的处理细节需在确定范围时商定。您希望助手使用哪些信息？'),
        'case_studies': (
            'Система уже внедрена у нескольких клиентов, но мы не можем раскрывать их имена и детали проектов. Общение с агентом можно проверить здесь, а демонстрацию под вашу задачу — запросить у Александра. Какой процесс вы хотите проверить?',
            'The system has been deployed for several clients, but we cannot disclose their names or project details. Try the agent here or ask Alexander for a demonstration tailored to your task. Which process would you like to test?',
            '系统已为多位客户部署，但我们不能公开客户名称或项目细节。您可以在这里体验对话，或向亚历山大申请针对需求的演示。您想测试哪个流程？'),
        'contract': (
            'Оплату и условия договора обсуждаете лично с Александром. Для действующих клиентов сохраняются текущие согласованные условия, если изменения отдельно не согласованы. Хотите оставить заявку на консультацию?',
            'Payment and contract terms are discussed personally with Alexander. Existing clients continue on their current agreed terms unless changes are agreed separately. Would you like to leave a consultation request?',
            '付款及合同条款请与亚历山大本人商谈。现有客户默认继续采用当前已约定条款，除非另行协商变更。需要提交咨询申请吗？'),
        'voice_customization': (
            'В отдельном проекте можно воссоздать голос по образцу с разрешения его владельца; демонстрация доступна по запросу. Сходство и качество оцениваем на ваших фразах, возможна более качественная озвучка, чем в этом демо. Какой голос вы хотели бы услышать?',
            'A custom project can recreate a voice from a sample with its owner’s permission; a demonstration is available on request. Similarity and quality are evaluated on your phrases, and synthesis can be better than this demo. What voice would you like to hear?',
            '定制项目可在声音所有者许可下按样本重建声音，可申请演示。相似度与质量需用您的句子评估，合成质量有可能优于当前演示。您希望使用怎样的声音？'),
        'modes': (
            'Ответ голосом включён по умолчанию, его можно выключить в чате. Нажмите микрофон, произнесите фразу и дождитесь паузы — я отвечу. Можно свободно переключаться между текстом и голосом.',
            'Spoken replies are enabled by default and can be turned off in chat. Press the microphone, say your message and pause for my reply. You can switch between text and voice.',
            '语音回复默认开启，可在聊天中关闭。点击麦克风，说完后稍作停顿，我就会回答。可随时切换文字和语音。')}
    extra = {
        'contract': ('Оплата и договор', ['оплата', 'договор', 'продление', 'условия оплаты', 'payment', 'contract', 'renewal', '付款', '合同']),
        'voice_customization': ('Индивидуальная озвучка и копирование голоса', ['клонирование', 'копировать голос', 'скопировать голос', 'другой голос', 'voice cloning', 'custom voice', '声音克隆', '定制声音'])}
    for id, (title, queries) in extra.items():
        if not any(c['id'] == id for c in chunks):
            chunks.append({'id': id, 'title': title, 'queries': queries})
    for c in chunks:
        if c['id'] in updates:
            c.update(answers=dict(zip(('ru', 'en', 'zh'), updates[c['id']])), source='Owner clarification, 2026-09-09', reviewed_at='2026-09-09')
    path.write_text('\n'.join(json.dumps(c, ensure_ascii=False, separators=(',', ':')) for c in chunks) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
