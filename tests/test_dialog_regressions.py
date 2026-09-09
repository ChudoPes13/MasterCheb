import asyncio

import pytest

from test_mastercheb import rig


@pytest.mark.parametrize('lang,yes', [('ru', 'да'), ('en', 'yes'), ('zh', '是')])
def test_bare_yes_does_not_start_lead(rig, lang, yes):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    dialog.start(session)
    asyncio.run(dialog.process(session, yes))
    assert session['stage'] is None


@pytest.mark.parametrize('lang,question', [
    ('ru', 'Какая погода на Марсе?'), ('en', 'Is the moon made of cheese?'),
    ('zh', '火星天气怎么样？'),
])
def test_unknown_question_never_becomes_lead_value(rig, lang, question):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    session['stage'] = 'company'
    asyncio.run(dialog.process(session, question))
    assert session['stage'] == 'company'
    assert 'company' not in session['lead']


@pytest.mark.parametrize('lang,question', [
    ('ru', 'Как изменить время работы помощника?'),
    ('en', 'Can I change the company knowledge base?'),
    ('zh', '如何修改公司知识库？'),
])
def test_discussing_changes_is_not_edit_command(rig, lang, question):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    asyncio.run(dialog.process(session, question))
    assert session['stage'] is None


@pytest.mark.parametrize('lang,question,needles', [
    ('ru', 'Сколько стоит и какие сроки внедрения?', ['50 000', '1–3']),
    ('en', 'How much does it cost and how long to implement?', ['50,000', '1–3']),
    ('zh', '费用是多少？实施需要多久？', ['50,000', '1–3']),
])
def test_two_questions_receive_two_facts(rig, lang, question, needles):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    response = asyncio.run(dialog.process(session, question))
    assert all(x in response['text'] for x in needles)


def test_unknown_question_does_not_trigger_common_word_match(rig):
    assert not rig[1].search('Какая погода на Марсе?')
    assert not rig[1].search('Is the moon made of cheese?')


@pytest.mark.parametrize('query,topic', [
    ('Скока стоет', 'pricing'), ('подержка', 'support'),
    ('сколько ждать запуска', 'timeline'), ('how mutch does it cost', 'pricing'),
    ('收费多少', 'pricing'),
])
def test_rephrasing_and_typos(rig, query, topic):
    found = rig[1].search(query)
    assert found and found[0]['id'] == topic


def test_declining_demo_does_not_offer_it_again(rig):
    store, _, dialog = rig
    session = store.create('ru', '2026-09-05')
    response = asyncio.run(dialog.process(session, 'Не хочу демо, сколько стоит подписка?'))
    assert '50 000' in response['text']
    assert session['stage'] is None
    assert 'индивидуального демо' not in response['text']


def test_followup_support(rig):
    store, _, dialog = rig
    session = store.create('ru', '2026-09-05')
    asyncio.run(dialog.process(session, 'On-Prem'))
    response = asyncio.run(dialog.process(session, 'А что после двух месяцев?'))
    assert 'сопровождение согласуется' in response['text']


@pytest.mark.parametrize('lang,text', [('ru','Спасибо'), ('en','Thanks'), ('zh','谢谢')])
def test_thanks_does_not_sell_or_fill_form(rig, lang, text):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    session['stage'] = 'company'
    answer = asyncio.run(dialog.process(session, text))['text']
    assert session['lead'] == {}
    assert session['stage'] == 'company'
    assert '?' not in answer and '？' not in answer


@pytest.mark.parametrize('lang,question', [
    ('en','What happens after two months?'), ('zh','两个月之后呢？')])
def test_support_followup_other_languages(rig, lang, question):
    store, _, dialog = rig
    session = store.create(lang, '2026-09-05')
    asyncio.run(dialog.process(session, 'On-Prem'))
    answer = asyncio.run(dialog.process(session, question))['text']
    expected = {'en':'Continued support is agreed', 'zh':'后续维护'}[lang]
    assert expected in answer
