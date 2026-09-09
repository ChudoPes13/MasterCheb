import re
from datetime import datetime, timezone

FIELDS = ('name', 'company', 'industry', 'task', 'contact', 'time')
TEXT = {
 'ru': {
  'greeting': 'Здравствуйте, я Маша — ИИ-консультант МастерЧеб. Расскажу, как такой помощник может отвечать вашим клиентам и собирать заявки. Что вы хотели бы узнать?',
  'name': 'Как к вам обращаться?', 'company': 'Как называется ваша компания?',
  'industry': 'В какой сфере вы работаете?', 'task': 'Какую задачу вы хотите поручить ИИ-помощнику?',
  'contact': 'Оставьте телефон, email или Telegram для связи с Александром.',
  'time': 'Когда вам удобно связаться — укажите день, время и часовой пояс?',
  'confirm': 'Проверьте заявку в карточке ниже и нажмите «Отправить заявку». Для изменения поля напишите «изменить имя», «изменить компанию», «изменить сферу», «изменить задачу», «изменить контакт» или «изменить время».',
  'done': 'Заявка сохранена для Александра — он свяжется с вами лично в указанное время, если оно будет доступно. Точное время встречи ещё не подтверждено. Можем продолжить: что ещё вы хотели бы узнать?',
  'fallback': 'Для точного ответа нужно уточнить вашу задачу с Александром. Он бесплатно разберёт процесс и предложит вариант внедрения. Хотите оставить заявку?',
  'invalid': 'Пожалуйста, укажите корректные данные для этого поля.',
  'cancel': 'Сбор заявки остановлен, её можно заполнить позже. Чем ещё помочь?',
  'thanks': 'Пожалуйста. Если появятся вопросы, я здесь.',
 },
 'en': {
  'greeting': "Hello, I'm Masha, MasterCheb's AI consultant. I can explain how an assistant can answer your customers and collect enquiries. What would you like to know?",
  'name': 'What is your name?', 'company': 'What is your company called?', 'industry': 'Which industry do you work in?',
  'task': 'What would you like an AI assistant to do?', 'contact': 'Please share a phone number, email or Telegram handle for Alexander.',
  'time': 'What day, time and time zone would suit you?',
  'confirm': 'Please review your request below and click “Send request”. To edit a field, type “change name”, “change company”, “change industry”, “change task”, “change contact” or “change time”.',
  'done': 'Your request has been saved for Alexander to follow up personally at your preferred time if available. The appointment time is not confirmed yet. What else would you like to know?',
  'fallback': 'Alexander can clarify your specific needs in a free consultation and suggest an implementation. Would you like to leave a request?',
  'invalid': 'Please enter valid information for this field.', 'cancel': 'Request collection is paused; you can return to it later. How else can I help?',
  'thanks': 'You’re welcome. I’m here if you need anything else.',
 },
 'zh': {
  'greeting': '您好，我是 MasterCheb 的人工智能顾问玛莎。我可以介绍智能助手如何回答客户问题并收集咨询申请。您想了解什么？',
  'name': '请问您的姓名？', 'company': '您的公司叫什么名字？', 'industry': '您从事哪个行业？',
  'task': '您希望智能助手处理什么任务？', 'contact': '请留下电话、邮箱或 Telegram 账号，方便亚历山大联系。',
  'time': '哪一天、什么时间方便联系，请注明时区？',
  'confirm': '请核对下方申请信息并点击“提交申请”。如需修改，请输入“修改姓名”“修改公司”“修改行业”“修改任务”“修改联系”或“修改时间”。',
  'done': '申请已为亚历山大保存，他会尽量按您希望的时间亲自联系。会面时间尚未最终确认。您还想了解什么？',
  'fallback': '亚历山大可以通过免费咨询明确您的具体需求并提出实施方案。需要提交申请吗？',
  'invalid': '请输入该字段的有效信息。', 'cancel': '已暂停收集申请，您可以稍后继续。还可以帮您什么？',
  'thanks': '不客气。有其他问题时可以继续问我。',
 }
}
def short(text):
    # Keep initials/URLs intact where possible; also handle Chinese punctuation.
    sentences = re.split(r'(?<=[!?。！？])\s*|(?<=\.)\s+(?=[A-ZА-Я])', text.strip())
    return ' '.join(sentences[:3])[:900]

def valid_field(key, value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        return False
    if key == 'contact':
        return bool(re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|@[a-zA-Z][\w]{3,}|https://t.me/[\w]+', value) or 10 <= len(re.sub(r'\D', '', value)) <= 15)
    return len(value.strip()) >= 2

class DialogManager:
    def __init__(self, rag, store, llm=None):
        self.rag, self.store, self.llm = rag, store, llm

    def response(self, s, text):
        text = short(text)
        s['messages'].append({'role': 'assistant', 'text': text, 'ts': datetime.now(timezone.utc).isoformat()})
        self.store.save(s)
        return {'event': 'assistant_response', 'text': text, 'lead': s['lead'], 'stage': s['stage'], 'submitted': s['submitted']}

    def start(self, s):
        return self.response(s, TEXT[s['language']]['greeting'])

    async def process(self, s, text, action=None):
        t = TEXT[s['language']]
        if action == 'submit':
            if not all(valid_field(k, s['lead'].get(k)) for k in FIELDS):
                return self.response(s, t['invalid'])
            s.update(submitted=True, stage=None)
            return self.response(s, t['done'])
        if action == 'lead':
            s['stage'] = next((k for k in FIELDS if not s['lead'].get(k)), 'confirm')
            return self.response(s, t[s['stage']])
        s['messages'].append({'role': 'user', 'text': text, 'ts': datetime.now(timezone.utc).isoformat()})
        lower = text.lower().strip()
        if re.fullmatch(r'(?:спасибо|благодарю|thanks|thank you|谢谢|多谢)[!！.。 ]*', lower):
            return self.response(s, t['thanks'])
        if re.fullmatch(r'(?:отмена|не хочу(?: (?:демо|заявку))?|cancel|stop|取消|停止|不要演示)[!！.。 ]*', lower):
            s['stage'] = None
            return self.response(s, t['cancel'])
        edits = {'name':r'имя|name|姓名', 'company':r'компан|company|公司', 'industry':r'сфер|industry|行业',
                 'task':r'задач|task|任务', 'contact':r'контакт|contact|联系', 'time':r'врем|time|时间'}
        if re.fullmatch(r'(?:изменить|исправить|change|edit|修改)\s*(?:имя|компанию|сферу|задачу|контакт|время|name|company|industry|task|contact|time|姓名|公司|行业|任务|联系|时间)[.!。 ]*', lower):
            for key, pattern in edits.items():
                if re.search(pattern, lower):
                    s['stage'] = key
                    s['submitted'] = False
                    return self.response(s, t[key])
        last_answer = next((m['text'] for m in reversed(s['messages']) if m['role'] == 'assistant'), '')
        offered = bool(re.search(r'оставить заявку\?|помочь оставить заявку\?|начнём с вашего имени\?|would you like to (?:leave|request)|shall we start with your name|需要(?:提交申请|帮您预约)吗', last_answer, re.I))
        affirmative = bool(re.fullmatch(r'(?:да|yes|是)[.!。 ]*', lower))
        explicit_lead = bool(re.fullmatch(r'(?:хочу демо|оставить заявку|записаться|request demo|book consultation|申请演示|预约咨询)[.!。 ]*', lower))
        if not s['stage'] and (explicit_lead or (affirmative and offered)):
            s['stage'] = next((k for k in FIELDS if not s['lead'].get(k)), 'confirm')
            return self.response(s, t[s['stage']])
        # Split explicit clauses; never combine unrelated runner-up search results.
        parts = [p.strip() for p in re.split(r'[?？;；]+|\s+(?:и|and)\s+(?=како|какие|сколько|что|how|what)|[，,]\s*', text, flags=re.I) if p.strip()]
        parts = [p for p in parts if not re.match(r'^(?:не хочу|не нужна?|no demo|不要演示)', p, re.I)]
        lookup = ' '.join(parts) or text
        support_followup = re.fullmatch(r'(?:(?:а )?(?:что )?после (?:двух|2) месяцев|what (?:happens )?after (?:two|2) months|两个月(?:之后|以后)呢)[?？!.。 ]*', lower)
        if support_followup and s.get('last_topic') in ('onprem', 'support'):
            lookup = 'поддержка'
        matches = self.rag.search(lookup)
        is_question = '?' in text or '？' in text or bool(re.match(r'^(сколько|как\b|что\b|а |можно|кто\b|зачем|почему|како|какие|how\b|what\b|who\b|can\b|why\b|is\b|does\b|多少|如何|什么|能否)', lower))
        if matches and (not s['stage'] or is_question):
            selected = []
            for part in parts:
                found = self.rag.search(part)
                if found and found[0]['id'] not in [c['id'] for c in selected]:
                    selected.append(found[0])
            if len(selected) > 1:
                s['last_topic'] = None
                return self.response(s, ' '.join(re.split(r'(?<=[。!?！？])\s*|(?<=\.)\s+', c['answers'][s['language']])[0] for c in selected[:3]))
            s['last_topic'] = matches[0]['id']
            return self.response(s, matches[0]['answers'][s['language']])
        if is_question and s['stage']:
            return self.response(s, t['fallback'].split('. ')[0] + '. ' + t[s['stage']])
        if s['stage'] in FIELDS:
            key = s['stage']
            if not valid_field(key, text):
                return self.response(s, t['invalid'] + ' ' + t[key])
            s['lead'][key] = text.strip()
            s['stage'] = next((k for k in FIELDS if not s['lead'].get(k)), 'confirm')
            return self.response(s, t[s['stage']])
        if s['stage'] == 'confirm':
            return self.response(s, t['confirm'])
        return self.response(s, t['fallback'])
