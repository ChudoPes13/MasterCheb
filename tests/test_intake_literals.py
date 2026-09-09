import asyncio
from pathlib import Path
from app.dialog import DialogManager
from app.rag import RagKnowledgeBase
from app.session_store import SessionStore

class FailingPlanner:
    async def plan(self,*args):
        raise AssertionError('Literal form values must not require LLM classification')

def test_intake_values_are_not_misread_as_faq_topics(tmp_path):
    store=SessionStore(tmp_path)
    dialog=DialogManager(RagKnowledgeBase(Path('docs/rag')),store,FailingPlanner())
    s=store.create('ru','test')
    async def run():
        await dialog.process(s,'',action='lead')
        for text,stage in [('Тестовый посетитель','company'),('Тестовая компания','industry'),('Услуги','task'),('Отвечать на вопросы клиентов','contact'),('demo@example.invalid','time'),('Завтра после обеда, Москва','confirm')]:
            response=await dialog.process(s,text)
            assert response['stage']==stage
        assert not s['submitted']
        response=await dialog.process(s,'',action='submit')
        assert response['submitted']
    asyncio.run(run())
