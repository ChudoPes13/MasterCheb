import asyncio
from pathlib import Path
from app.dialog import DialogManager
from app.rag import RagKnowledgeBase
from app.session_store import SessionStore

class Planner:
    result = None
    async def plan(self, *args):
        return self.result

def test_grounded_prices_context_and_intake(tmp_path):
    planner = Planner()
    store = SessionStore(tmp_path)
    dialog = DialogManager(RagKnowledgeBase(Path('docs/rag')), store, planner)
    s = store.create('ru', 'test')
    s['asked'] = ['example']
    async def run():
        planner.result = dict(kind='answer', topics=['pricing'], answer='Всё бесплатно навсегда.', next='invite', value='')
        response = await dialog.process(s, 'А сколько это обойдётся?')
        assert '50 000' in response['text'] and 'бесплатно навсегда' not in response['text']
        assert response['text'].count('?') == 1
        response = await dialog.process(s, 'Да')
        assert response['stage'] == 'name'
        planner.result = dict(kind='answer', topics=['materials'], answer='', next='example', value='')
        response = await dialog.process(s, 'А документы в каких форматах?')
        assert response['stage'] == 'name' and not response['lead']
        assert 'тысячи' in response['text'] and 'Как к вам обращаться?' in response['text']
        planner.result = dict(kind='field', topics=[], answer='', next='none', value='Выдуманное имя')
        await dialog.planned_response(s, 'Тестовое имя')
        assert not s['lead']
        planner.result['value'] = 'Тестовое имя'
        await dialog.process(s, 'Тестовое имя')
        assert s['lead']['name'] == 'Тестовое имя'
    asyncio.run(run())

def test_decline_and_model_outage(tmp_path):
    planner = Planner()
    store = SessionStore(tmp_path)
    dialog = DialogManager(RagKnowledgeBase(Path('docs/rag')), store, planner)
    s = store.create('ru', 'test')
    async def run():
        await dialog.process(s, 'не хочу заявку')
        planner.result = dict(kind='answer', topics=['identity'], answer='', next='invite', value='')
        response = await dialog.process(s, 'Что ты умеешь?')
        assert 'заявку?' not in response['text']
        planner.result = None
        response = await dialog.process(s, 'Сколько стоит?')
        assert '50 000' in response['text']
    asyncio.run(run())

def test_smalltalk_is_not_an_unknown_commercial_question(tmp_path):
    store=SessionStore(tmp_path)
    dialog=DialogManager(RagKnowledgeBase(Path('docs/rag')),store,Planner())
    s=store.create('ru','test')
    response=asyncio.run(dialog.process(s,'Привет, как настроение?'))
    assert 'Я готова помочь' in response['text']
    assert 'Александр' not in response['text']
    assert response['text'].count('?')==1

def test_asking_mashas_name_does_not_start_lead_collection(tmp_path):
    store=SessionStore(tmp_path);planner=Planner()
    planner.result=dict(kind='lead',topics=[],answer='',next='none',value='')
    dialog=DialogManager(RagKnowledgeBase(Path('docs/rag')),store,planner)
    s=store.create('ru','test')
    response=asyncio.run(dialog.process(s,'Как к вам обращаться?'))
    assert 'Я Маша' in response['text'] and response['stage'] is None
