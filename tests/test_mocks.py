import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mocks'))

def test_apply_diff():
    from apply_diff import apply_diff
    result = apply_diff(path='test.py', diff='<<<<<<< SEARCH\n=======\n>>>>>>> REPLACE')
    assert result['status'] == 'success'
    assert result['path'] == 'test.py'
    print('apply_diff test passed')

def test_ask_followup_question():
    from ask_followup_question import ask_followup_question
    result = ask_followup_question(question='test?', follow_up=[{'text': 'yes', 'mode': None}])
    assert result['status'] == 'success'
    print('ask_followup_question test passed')

def test_attempt_completion():
    from attempt_completion import attempt_completion
    result = attempt_completion(result='test')
    assert result['status'] == 'success'
    print('attempt_completion test passed')

def test_execute_command():
    from execute_command import execute_command
    result = execute_command(command='echo hello', cwd=None, timeout=5)
    assert result['status'] == 'success'
    print('execute_command test passed')

def test_list_files():
    from list_files import list_files
    result = list_files(path='.', recursive=False)
    assert result['status'] == 'success'
    print('list_files test passed')

def test_read_command_output():
    from read_command_output import read_command_output
    result = read_command_output(artifact_id='test.txt', search='test', offset=0, limit=10)
    assert result['status'] == 'success'
    print('read_command_output test passed')

def test_read_file():
    from read_file import read_file
    result = read_file(path='test.py', mode='slice', offset=1, limit=10, indentation={})
    assert result['status'] == 'success'
    print('read_file test passed')

def test_search_files():
    from search_files import search_files
    result = search_files(path='.', regex='test', file_pattern='*.py')
    assert result['status'] == 'success'
    print('search_files test passed')

if __name__ == '__main__':
    test_apply_diff()
    test_ask_followup_question()
    test_attempt_completion()
    test_execute_command()
    test_list_files()
    test_read_command_output()
    test_read_file()
    test_search_files()
    print('All tests passed!')