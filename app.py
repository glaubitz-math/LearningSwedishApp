from flask import Flask, request, render_template, redirect, url_for, jsonify, session
from urllib.parse import urlencode
import sqlite3, random, re, secrets, json
from random import choice

words_test = 5

def normalize_word(word):
    word = word.lower()
    word = re.sub(r'[.,]', '', word)  # Remove dots and commas
    word = re.sub(r'^to\s+', '', word)  # Remove 'to' at the beginning
    return word


app = Flask(__name__)

app.secret_key = secrets.token_hex(16)  # Generates a 32-character hexadecimal string


# Initialize the database
def init_db():
    with sqlite3.connect('database.db') as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                swedish_word TEXT NOT NULL,
                german_word TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                word_id INTEGER PRIMARY KEY,
                correct_attempts INTEGER DEFAULT 0,
                incorrect_attempts INTEGER DEFAULT 0,
                FOREIGN KEY(word_id) REFERENCES vocabulary(id)
            )
        ''')
        # Conjugations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conjugations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER,
                infinitive TEXT,
                imperative TEXT,
                present TEXT,
                preteritum TEXT,
                supinum TEXT,
                FOREIGN KEY(word_id) REFERENCES vocabulary(id)
            )
        ''')

        # Declensions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS declensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER,
                indefinite_singular TEXT,
                definite_singular TEXT,
                indefinite_plural TEXT,
                definite_plural TEXT,
                FOREIGN KEY(word_id) REFERENCES vocabulary(id)
            )
        ''')

        conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-word', methods=['POST'])
def add_word():
    swedish_word = request.form['swedish_word']
    german_word = request.form['german_word']
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO vocabulary (swedish_word, german_word) VALUES (?, ?)', (swedish_word, german_word))
        word_id = cursor.lastrowid
        cursor.execute('INSERT INTO attempts (word_id) VALUES (?)', (word_id,))
        conn.commit()

    return redirect(url_for('index'))

@app.route('/vocabulary')
def vocabulary():
    # Get sorting parameters
    sort_by = request.args.get('sort_by', 'swedish_word')
    sort_order = request.args.get('sort_order', 'asc')

    # Get pagination parameters
    per_page = int(request.args.get('per_page', 25))  # Default to 25 items per page
    page = int(request.args.get('page', 1))
    offset = (page - 1) * per_page

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        # Get the total number of vocabulary items
        cursor.execute('SELECT COUNT(*) FROM vocabulary')
        total_items = cursor.fetchone()[0]

        # Get the sorted vocabulary items for the current page
        query = f'''
            SELECT v.swedish_word, v.german_word, 
                   COALESCE(a.correct_attempts, 0) AS correct_attempts, 
                   COALESCE(a.incorrect_attempts, 0) AS incorrect_attempts,
                   v.id
            FROM vocabulary v
            LEFT JOIN attempts a ON v.id = a.word_id
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, (per_page, offset))
        words = cursor.fetchall()

        # Calculate totals
        cursor.execute('SELECT COUNT(*), SUM(correct_attempts), SUM(incorrect_attempts) FROM attempts')
        totals = cursor.fetchone()
        total_words = totals[0]
        total_correct_attempts = totals[1] if totals[1] is not None else 0
        total_incorrect_attempts = totals[2] if totals[2] is not None else 0

        # Calculate the number of words not guessed correctly
        cursor.execute('SELECT COUNT(*) FROM vocabulary v LEFT JOIN attempts a ON v.id = a.word_id WHERE a.correct_attempts = 0')
        not_guessed_correctly = cursor.fetchone()[0]

    total_pages = (total_items + per_page - 1) // per_page  # Calculate total pages

    return render_template('vocabulary.html', 
                           words=words, 
                           page=page, 
                           per_page=per_page, 
                           total_pages=total_pages, 
                           total_words=total_words, 
                           total_correct_attempts=total_correct_attempts, 
                           total_incorrect_attempts=total_incorrect_attempts, 
                           not_guessed_correctly=not_guessed_correctly, 
                           sort_by=sort_by, 
                           sort_order=sort_order)

@app.route('/add_grammar')
def add_grammar():
    return render_template('add_grammar.html')

@app.route('/get_suggestions')
def get_suggestions():
    search_term = request.args.get('q', '').lower()
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        # Filter words that match the search term
        cursor.execute("SELECT id, swedish_word FROM vocabulary WHERE LOWER(swedish_word) LIKE ?", (f'%{search_term}%',))
        words = cursor.fetchall()

    suggestions = [{'id': word[0], 'word': word[1]} for word in words]
    return jsonify(suggestions)


@app.route('/add_conjugation/<int:word_id>', methods=['GET', 'POST'])
def add_conjugation(word_id):
    if request.method == 'POST':
        infinitive = request.form['infinitive']
        imperative = request.form['imperative']
        present = request.form['present']
        preteritum = request.form['preteritum']
        supinum = request.form['supinum']

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conjugations (word_id, infinitive, imperative, present, preteritum, supinum)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (word_id, infinitive, imperative, present, preteritum, supinum))
            conn.commit()

        return redirect(url_for('summary_conjugation', word_id=word_id))

    # Fetch the word from the vocabulary table
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT swedish_word FROM vocabulary WHERE id = ?', (word_id,))
        word = cursor.fetchone()[0]

    return render_template('add_conjugation.html', word=word, word_id=word_id)


@app.route('/add_declension/<int:word_id>', methods=['GET', 'POST'])
def add_declension(word_id):
    if request.method == 'POST':
        indefinite_singular = request.form['indefinite_singular']
        definite_singular = request.form['definite_singular']
        indefinite_plural = request.form['indefinite_plural']
        definite_plural = request.form['definite_plural']

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO declensions (word_id, indefinite_singular, definite_singular, indefinite_plural, definite_plural)
                VALUES (?, ?, ?, ?, ?)
            ''', (word_id, indefinite_singular, definite_singular, indefinite_plural, definite_plural))
            conn.commit()

        return redirect(url_for('summary_declension', word_id=word_id))

    # Fetch the word from the vocabulary table
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT swedish_word FROM vocabulary WHERE id = ?', (word_id,))
        word = cursor.fetchone()[0]

    return render_template('add_declension.html', word=word, word_id=word_id)

@app.route('/summary_conjugation/<int:word_id>')
def summary_conjugation(word_id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        # Fetch the word
        cursor.execute('SELECT swedish_word FROM vocabulary WHERE id = ?', (word_id,))
        word = cursor.fetchone()[0]

        # Fetch the conjugation
        cursor.execute('SELECT * FROM conjugations WHERE word_id = ?', (word_id,))
        conjugation = cursor.fetchone()
    
    return render_template('summary_conjugation.html', word=word, conjugation=conjugation)

@app.route('/summary_declension/<int:word_id>')
def summary_declension(word_id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        # Fetch the word
        cursor.execute('SELECT swedish_word FROM vocabulary WHERE id = ?', (word_id,))
        word = cursor.fetchone()[0]

        # Fetch the declension
        cursor.execute('SELECT * FROM declensions WHERE word_id = ?', (word_id,))
        declension = cursor.fetchone()
    
    return render_template('summary_declension.html', word=word, declension=declension)

@app.route('/view_grammar')
def view_grammar():
    # Get parameters for pagination and sorting
    per_page = int(request.args.get('per_page', 10))  # Default to 10 items per page
    page = int(request.args.get('page', 1))
    offset = (page - 1) * per_page
    sort_by = request.args.get('sort_by', 'swedish_word')
    sort_order = request.args.get('sort_order', 'asc')
    section = request.args.get('section', 'conjugations')  # Determine which section is being viewed

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        conjugations = []
        declensions = []
        total_conjugations = 0
        total_declensions = 0


        # Fetch conjugations with sorting and pagination
        query_conjugations = f'''
            SELECT c.id, v.swedish_word, c.infinitive, c.imperative, c.present, c.preteritum, c.supinum
            FROM conjugations c
            JOIN vocabulary v ON c.word_id = v.id
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query_conjugations, (per_page, offset))
        conjugations = cursor.fetchall()

        cursor.execute('SELECT COUNT(*) FROM conjugations')
        total_conjugations = cursor.fetchone()[0]


        # Fetch declensions with sorting and pagination
        query_declensions = f'''
            SELECT d.id, v.swedish_word, d.indefinite_singular, d.definite_singular, d.indefinite_plural, d.definite_plural
            FROM declensions d
            JOIN vocabulary v ON d.word_id = v.id
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query_declensions, (per_page, offset))
        declensions = cursor.fetchall()

        cursor.execute('SELECT COUNT(*) FROM declensions')
        total_declensions = cursor.fetchone()[0]

    total_pages_conjugations = (total_conjugations + per_page - 1) // per_page
    total_pages_declensions = (total_declensions + per_page - 1) // per_page

    print(conjugations)
    print(declensions)

    return render_template('view_grammar.html', 
                           conjugations=conjugations, 
                           declensions=declensions, 
                           page=page, 
                           per_page=per_page, 
                           total_pages_conjugations=total_pages_conjugations, 
                           total_pages_declensions=total_pages_declensions, 
                           sort_by=sort_by, 
                           sort_order=sort_order, 
                           section=section)


@app.route('/delete_conjugation/<int:id>', methods=['POST'])
def delete_conjugation(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM conjugations WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('view_grammar'))

@app.route('/delete_declension/<int:id>', methods=['POST'])
def delete_declension(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM declensions WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('view_grammar'))



@app.route('/test', methods=['GET'])
def test():
    test_type = request.args.get('type', 'random')  # Default to 'random' if not specified
    
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        
        # Fetch words for Random test (select both columns, and randomize direction)
        cursor.execute('SELECT id, swedish_word, german_word FROM vocabulary ORDER BY RANDOM() LIMIT ?', (words_test,))
        words = cursor.fetchall()

        # Modify the words list for random direction in the random test
        if test_type == 'random':
            randomized_words = []
            for word in words:
                if random.choice([True, False]):
                    # English to Swedish
                    randomized_words.append((word[0], word[2], word[1]))  # (id, english_word, swedish_word)
                else:
                    # Swedish to English
                    randomized_words.append((word[0], word[1], word[2]))  # (id, swedish_word, english_word)
            words = randomized_words
        elif test_type == 'english_to_swedish':
            words = [(word[0], word[2], word[1]) for word in words]  # (id, english_word, swedish_word)
        elif test_type == 'swedish_to_english':
            words = [(word[0], word[1], word[2])]  # (id, swedish_word, german_word)

    return render_template('test.html', words=words, test_type=test_type)

@app.route('/test-zero-attempts')
def test_zero_attempts():
    num_words = int(request.args.get('num_words', 5))  # Default to 5 words if not specified
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.id, v.swedish_word, v.german_word
            FROM vocabulary v
            LEFT JOIN attempts a ON v.id = a.word_id
            WHERE a.correct_attempts = 0
            ORDER BY RANDOM()
            LIMIT ?
        ''', (num_words,))
        words = cursor.fetchall()

    return render_template('test.html', words=words, random=random, num_words=num_words)


@app.route('/grammar_test')
def grammar_test():
    words_test = 5  # Number of words to test for each section
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        # Select random conjugations
        cursor.execute('SELECT id, infinitive, imperative, present, preteritum, supinum FROM conjugations ORDER BY RANDOM() LIMIT ?', (words_test,))
        conjugations = cursor.fetchall()

        # Select random declensions
        cursor.execute('SELECT id, indefinite_singular, definite_singular, indefinite_plural, definite_plural FROM declensions ORDER BY RANDOM() LIMIT ?', (words_test,))
        declensions = cursor.fetchall()

    # Prepare the test questions by pre-filling one random field and leaving the rest empty
    conjugation_test = []
    for conjugation in conjugations:
        fields = ['infinitive', 'imperative', 'present', 'preteritum', 'supinum']
        filled_field = choice(fields)
        question = {field: conjugation[i+1] if field == filled_field else '' for i, field in enumerate(fields)}
        question['id'] = conjugation[0]
        question['filled_field'] = filled_field
        conjugation_test.append(question)

    declension_test = []
    for declension in declensions:
        fields = ['indefinite_singular', 'definite_singular', 'indefinite_plural', 'definite_plural']
        filled_field = choice(fields)
        question = {field: declension[i+1] if field == filled_field else '' for i, field in enumerate(fields)}
        question['id'] = declension[0]
        question['filled_field'] = filled_field
        declension_test.append(question)

    return render_template('grammar_test.html', conjugation_test=conjugation_test, declension_test=declension_test)

@app.route('/submit_grammar_test', methods=['POST'])
def submit_grammar_test():
    conjugation_answers = request.form.getlist('conjugation_answers[]')
    conjugation_ids = request.form.getlist('conjugation_ids[]')
    conjugation_fields = request.form.getlist('conjugation_fields[]')
    print(conjugation_fields)

    declension_answers = request.form.getlist('declension_answers[]')
    declension_ids = request.form.getlist('declension_ids[]')
    declension_fields = request.form.getlist('declension_fields[]')

    correct_conjugations = []
    incorrect_conjugations = []

    correct_declensions = []
    incorrect_declensions = []

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        # Check conjugation answers
        print(conjugation_ids)
        for i in range(len(conjugation_ids)):
            cursor.execute(f'SELECT * FROM conjugations WHERE id = ?', (conjugation_ids[i],))
            correct_answer = cursor.fetchone()[2:]
            user_answer = tuple(conjugation_answers[5*i:5*(i+1)])
            if user_answer == correct_answer:
                correct_conjugations.append((conjugation_ids[i], user_answer))
            else:
                incorrect_conjugations.append((conjugation_ids[i], correct_answer, user_answer))

        # Check declension answers
        for i in range(len(declension_ids)):
            field_to_check = declension_fields[i]
            cursor.execute(f'SELECT * FROM declensions WHERE id = ?', (declension_ids[i],))
            correct_answer = cursor.fetchone()[2:]
            user_answer = tuple(declension_answers[4*i:4*(i+1)])
            if user_answer == correct_answer:
                correct_declensions.append((declension_ids[i], user_answer))
            else:
                incorrect_declensions.append((declension_ids[i], correct_answer, user_answer))

    return render_template('grammar_review.html', 
                            correct_conjugations=correct_conjugations, 
                            incorrect_conjugations=incorrect_conjugations, 
                            correct_declensions=correct_declensions, 
                            incorrect_declensions=incorrect_declensions)



@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    word_ids = request.form.getlist('word_ids[]')
    answers = request.form.getlist('answers[]')
    correct_translations = request.form.getlist('correct_translations[]')
    questions = request.form.getlist('questions[]')
    num_words = words_test #int(request.form.get('num_words', 5))  # This should be passed as a hidden field in the form

    results = []
    incorrect_words = []

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        
        for i, word_id in enumerate(word_ids):
            user_answer = normalize_word(answers[i])
            correct_answer = normalize_word(correct_translations[i])
            is_correct = user_answer == correct_answer

            result = {
                'word_id': word_id,
                'user_translation': answers[i],
                'correct_translation': correct_translations[i],
                'question': questions[i],
                'is_correct': is_correct
            }
            results.append(result)
            
            if is_correct:
                cursor.execute('UPDATE attempts SET correct_attempts = correct_attempts + 1 WHERE word_id = ?', (word_id,))
            else:
                incorrect_words.append(result)

        conn.commit()

    # Calculate number of correct words
    incorrect_count = len(incorrect_words)
    correct_count = num_words - incorrect_count

    # If all words are correct, redirect to the awesome_job page
    if incorrect_count == 0:
        return redirect(f'/awesome_job')

    return render_template('review.html', results=results, incorrect_words=incorrect_words, correct_count=correct_count, incorrect_count=incorrect_count)



@app.route('/train_again', methods=['POST'])
def train_again():
    word_ids = request.form.getlist('word_ids[]')
    results_json = request.form.get('results')

    # Deserialize the JSON string into a Python object
    try:
        results = json.loads(results_json) if results_json else []
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        results = []

    correct_count = 0
    incorrect_count = 0
    incorrect_words = []
    correct_words = []

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        for word_id in word_ids:
            result = request.form.get(f'result_{word_id}')

            if result == 'correct':
                cursor.execute('UPDATE attempts SET correct_attempts = correct_attempts + 1 WHERE word_id = ?', (word_id,))
            elif result == 'incorrect':
                cursor.execute('UPDATE attempts SET incorrect_attempts = incorrect_attempts + 1 WHERE word_id = ?', (word_id,))
                incorrect_count += 1
                cursor.execute('SELECT swedish_word, german_word FROM vocabulary WHERE id = ?', (word_id,))
                word_data = cursor.fetchone()
                incorrect_words.append(word_data)

        # Handle automatically recognized correct/incorrect words from the original results
        for result in results:
            if str(result['word_id']) not in word_ids:
                if result['is_correct']:
                    cursor.execute('UPDATE attempts SET correct_attempts = correct_attempts + 1 WHERE word_id = ?', (result['word_id'],))
                else:
                    incorrect_words.append((result['question'], result['correct_translation']))

        conn.commit()

    # If all answers are correct after retraining, redirect to the awesome_job page
    if incorrect_count == 0:
        return redirect(f'/awesome_job')


    # Flatten the list into multiple parameters
    params_incorrect = []
    for word in incorrect_words:
        params_incorrect.append(('incorrect_words[]', f'{word[0]} / {word[1]}'))

    # Encode the parameters into a query string
    query_string = urlencode(params_incorrect)

    return redirect(f'/summary?{query_string}')


@app.route('/awesome_job')
def awesome_job():
    return render_template('awesome_job.html')


@app.route('/submit_train_again', methods=['POST'])
def submit_train_again():
    train_word_ids = request.form.getlist('train_word_ids[]')
    all_word_ids = request.form.getlist('word_ids[]')

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        # Update the incorrect attempts for words that are being trained again
        for word_id in train_word_ids:
            cursor.execute('UPDATE attempts SET incorrect_attempts = incorrect_attempts + 1 WHERE word_id = ?', (word_id,))

        # Update the correct attempts for words that are not being trained again
        words_not_trained_again = set(all_word_ids) - set(train_word_ids)
        for word_id in words_not_trained_again:
            cursor.execute('UPDATE attempts SET correct_attempts = correct_attempts + 1 WHERE word_id = ?', (word_id,))

        conn.commit()

    return redirect(url_for('summary'))





@app.route('/summary')
def summary():
    incorrect_words = request.args.getlist('incorrect_words[]')

    incorrect_count = len(incorrect_words)
    correct_count = words_test - incorrect_count
    

    return render_template('summary.html', correct_count=correct_count, incorrect_count=incorrect_count, incorrect_words=incorrect_words)

@app.route('/delete-word/<int:word_id>', methods=['POST'])
def delete_word(word_id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM attempts WHERE word_id = ?', (word_id,))
        cursor.execute('DELETE FROM vocabulary WHERE id = ?', (word_id,))
        conn.commit()
    return redirect(url_for('vocabulary'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
