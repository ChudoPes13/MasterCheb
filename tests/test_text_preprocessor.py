from app.text_preprocessor import RussianTextPreprocessor
def test_brand_and_price():
 p=RussianTextPreprocessor()
 assert 'Мастер Чеб' in p.preprocess('МастерЧеб')
 assert 'пятьдесят тысяч' in p.preprocess('50 000 рублей')
 assert 'Ксения' == p.preprocess('Ксения')

def test_owner_approved_surname_accent():
 p=RussianTextPreprocessor()
 assert p.preprocess('Мастеров, Мастерова, Мастерову') == 'М+астеров, М+астерова, М+астерову'
