from flask import Flask, request, render_template, redirect, url_for
import sqlite3
import random

app = Flask(__name__)

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
    sort_by = request.args.get('sort_by', 'swedish_word')  # Default sort by Swedish word
    sort_order = request.args.get('sort_order', 'asc')  # Default sort order ascending

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        query = f'''
            SELECT v.swedish_word, v.german_word, 
                   COALESCE(a.correct_attempts, 0) AS correct_attempts, 
                   COALESCE(a.incorrect_attempts, 0) AS incorrect_attempts,
                   v.id
            FROM vocabulary v
            LEFT JOIN attempts a ON v.id = a.word_id
            ORDER BY {sort_by} {sort_order}
        '''
        cursor.execute(query)
        words = cursor.fetchall()
    
    return render_template('vocabulary.html', words=words, sort_by=sort_by, sort_order=sort_order)


#@app.route('/test')
#def test():
#    with sqlite3.connect('database.db') as conn:
#        cursor = conn.cursor()
#        cursor.execute('SELECT * FROM vocabulary ORDER BY RANDOM() LIMIT 1')
#        word = cursor.fetchone()
#        word_id, swedish_word, german_word = word
#        language = random.choice(['swedish', 'german'])
#        if language == 'swedish':
#            prompt_word = swedish_word
#            correct_translation = german_word
#        else:
#            prompt_word = german_word
#            correct_translation = swedish_word

#    return render_template('test.html', word_id=word_id, prompt_word=prompt_word, correct_translation=correct_translation, language=language)

@app.route('/test')
def test():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM vocabulary ORDER BY RANDOM() LIMIT 100')
        words = cursor.fetchall()

    return render_template('test.html', words=words, random=random)


@app.route('/submit-answers', methods=['POST'])
def submit_answers():
    answers = request.form.getlist('answers[]')
    word_ids = request.form.getlist('word_ids[]')
    correct_translations = request.form.getlist('correct_translations[]')
    questions = request.form.getlist('questions[]')

    results = []
    for answer, word_id, correct_translation, question in zip(answers, word_ids, correct_translations, questions):
        results.append({
            'word_id': word_id,
            'user_translation': answer,
            'correct_translation': correct_translation,
            'question': question
        })

    print("Results:", results)  # Debug print

    return render_template('review.html', results=results)



@app.route('/update-attempts', methods=['POST'])
def update_attempts():
    word_ids = request.form.getlist('word_ids[]')
    correct_count = 0
    total_count = len(word_ids)
    incorrect_words = []

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        for word_id in word_ids:
            result = request.form.get(f'result_{word_id}')
            cursor.execute('SELECT swedish_word, german_word FROM vocabulary WHERE id = ?', (word_id,))
            word = cursor.fetchone()
            swedish_word, german_word = word[0], word[1]

            if result == 'correct':
                cursor.execute('UPDATE attempts SET correct_attempts = correct_attempts + 1 WHERE word_id = ?', (word_id,))
                correct_count += 1
            elif result == 'incorrect':
                cursor.execute('UPDATE attempts SET incorrect_attempts = incorrect_attempts + 1 WHERE word_id = ?', (word_id,))
                cursor.execute('SELECT swedish_word, german_word FROM vocabulary WHERE id = ?', (word_id,))
                word = cursor.fetchone()
                question = swedish_word if random.choice(['swedish', 'german']) == 'swedish' else german_word
                correct_translation = german_word if question == swedish_word else swedish_word
                incorrect_words.append({
                    'word_id': word_id,
                    'question': question,
                    'correct_translation': correct_translation
                })
        conn.commit()

    return render_template('summary.html', correct_count=correct_count, total_count=total_count, incorrect_words=incorrect_words)


#   return render_template('result.html', result=result, correct_translation=correct_translation)

@app.route('/retry-incorrect-words', methods=['POST'])
def retry_incorrect_words():
    word_ids = request.form.getlist('word_ids[]')
    retyped_answers = request.form.getlist('retyped_answers[]')
    correct_translations = request.form.getlist('correct_translations[]')

    results = []
    for retyped_answer, word_id, correct_translation in zip(retyped_answers, word_ids, correct_translations):
        results.append({
            'word_id': word_id,
            'user_translation': retyped_answer,
            'correct_translation': correct_translation,
            'question': correct_translation  # Assuming the question is the correct translation
        })

    return render_template('review.html', results=results)


@app.route('/summary/<int:correct_count>/<int:total_count>')
def summary(correct_count, total_count):
    return render_template('summary.html', correct_count=correct_count, total_count=total_count)


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
