import unittest
import os
import json
from datetime import datetime

from main import DependencyVisualizer


class TestDependencyVisualizer(unittest.TestCase):

    def setUp(self):
        # Папка для тестов
        self.test_dir = 'test_git'

        # Конфигурационные данные
        self.config_data = {
            "repo_path": "C:/Users/marma/PycharmProjects/DependencyVisualizer/test_git",
            "branch": "master",
            "visualizer_program_path": "C:/Program Files/Graphviz/bin/dot.exe",
            "graph_output_path": "C:/Users/marma/PycharmProjects/DependencyVisualizer/test_git/graphs",
            "target_file": ".gitignore"
        }

        # Сохраняем конфигурацию в config.json
        with open(os.path.join('config.json'), 'w') as f:
            json.dump(self.config_data, f, indent=4)

        self.visualizer = DependencyVisualizer('config.json')

    def test_parse_object(self):
        # Данные для тестирования
        test_data = [
            # Blob
            {
                "object_hash": "191381ee74dec49c89f99a62d055cb1058ba0de9",
                "expected_result": {'label': '[blob] 191381', 'children': []}
            },
            # Tree
            {
                "object_hash": "d0b8a8d944368025e6381d05ac2e356861f9e016",
                "expected_result": {
                    'label': '[tree] d0b8a8',
                    'children': [
                        {'label': '[blob] 191381\n.gitignore', 'children': []},
                        {'label': '[blob] 02ffeb\nconfig.json', 'children': []},
                        {'label': '[blob] c51498\ntests.py', 'children': []}
                    ]
                }
            },
            # Commit
            {
                "object_hash": "883996d4b1c2c5af3bd7db3c0738abc5e0233755",
                "expected_result": {
                    'label': '[commit] 883996\nAuthor: Marmazeev Dmitriy\nDate: 2024-11-29 16:26:33',
                    'children': [
                        {
                            'label': '[tree] d0b8a8',
                            'children': [
                                {'label': '[blob] 191381\n.gitignore', 'children': []},
                                {'label': '[blob] 02ffeb\nconfig.json', 'children': []},
                                {'label': '[blob] c51498\ntests.py', 'children': []}
                            ]
                        }
                    ]
                }
            }
        ]

        for i in range(0, len(test_data)):
            self.assertEqual(self.visualizer.parse_object(test_data[i]["object_hash"]), test_data[i]["expected_result"])

    def test_parse_commit(self):
        """Тестируем парсинг коммита"""
        # Пример содержимого коммита
        raw_commit = (b'tree f300f2b31af5cecc30958bdca2b7dc4920c64d5a\nauthor Who am I <dmarmaz@yandex.ru> '
                      b'1732640204 +0300\ncommitter Who am I <WhoAmI> 1732640204 '
                      b'+0300\n\n\xd0\xb4\xd0\xbe\xd0\xb1\xd0\xb0\xd0\xb2\xd0\xbb\xd0\xb5\xd0\xbd '
                      b'\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xbe\xd0\xb9 readme \xd1\x84\xd0\xb0\xd0\xb9\xd0\xbb\n')

        # Ожидаемый результат
        expected_result = {'parents': [], 'tree': 'f300f2b31af5cecc30958bdca2b7dc4920c64d5a', 'author_name': 'Who am I',
                           'author_date': '2024-11-26 16:56:44'}

        # Вызываем метод
        result = self.visualizer.parse_commit(raw_commit)

        # Проверяем соответствие результата ожиданиям
        self.assertEqual(result, expected_result)

    def test_parse_tree(self):
        """Тестируем парсинг tree-объекта."""
        visualizer = DependencyVisualizer('config.json')
        raw_tree = (
            b'100644 file1\x00\x12\x34\x56\x78\x90\xab\xcd\xef\x12\x34\x56\x78\x90\xab\xcd\xef\x12\x34'
            b'100644 file2\x00\x98\x76\x54\x32\x10\xfe\xdc\xba\x98\x76\x54\x32\x10\xfe\xdc\xba\x98\x76'
        )

        def mock_parse_object(hash_val, description=None, author_data=None):
            return {
                'label': f'[blob] {hash_val[:6]}',
                'description': description,
                'children': []
            }

        # Мокаем parse_object для изоляции теста
        visualizer.parse_object = mock_parse_object

        expected_result = [
            {'label': '[blob] 123456', 'description': 'file1', 'children': []},
            {'label': '[blob] 987654', 'description': 'file2', 'children': []}
        ]

        result = visualizer.parse_tree(raw_tree, None)
        self.assertEqual(result, expected_result)

    def test_get_last_commit(self):
        """Тестируем получение последнего коммита"""

        # Предполагаем, что в тестовом репозитории коммит — это строка, которая должна быть возвращена
        # Подставьте нужный результат в зависимости от структуры тестового репозитория
        last_commit = self.visualizer.get_last_commit()

        # Ожидаем, что результат — это строка с хэшем коммита
        self.assertIsInstance(last_commit, str, "Последний коммит должен быть строкой!")
        self.assertRegex(last_commit, r"^[a-f0-9]{40}$", "Неверный формат хэша коммита!")

    def test_add_one_to_parents_if_target_found(self):
        tree = self.visualizer.parse_object(self.visualizer.get_last_commit())
        self.visualizer.add_one_to_parents_if_target_found(tree, self.config_data["target_file"])

        def check_start_with_one(obj, start_with_one):
            if "[commit]" in obj["label"]:
                for child in obj["children"]:
                    check_start_with_one(child, obj["label"].startswith("1"))
            if "[tree]" in obj["label"]:
                self.assertEqual(start_with_one, obj["label"].startswith("1"))
                have_child_start_with_one = False
                for child in obj["children"]:
                    if "[blob]" not in child["label"]:
                        check_start_with_one(child, start_with_one)
                    else:
                        have_child_start_with_one = have_child_start_with_one or child["label"].startswith("1")
                self.assertTrue(have_child_start_with_one)

        check_start_with_one(tree, tree["label"].startswith("1"))

    def test_generate_dot_filtered(self):
        """Тестируем генерацию фильтрованного DOT файла"""

        os.makedirs(self.config_data['graph_output_path'], exist_ok=True)

        # Проверяем, что файл будет создан
        output_dot_path = self.config_data['graph_output_path'] + "/filtered_graph.dot"

        # Вызываем метод, который должен генерировать DOT файл
        self.visualizer.generate_dot_filtered(self.config_data["target_file"], output_dot_path)

        # Проверяем, что файл DOT был создан
        self.assertTrue(os.path.exists(output_dot_path), "DOT файл не был создан!")

    def test_generate_png_from_dot(self):
        """Тестируем генерацию PNG файла из DOT"""

        # Проверяем, что файл будет создан
        output_png_path = os.path.join("graphs",
                                       "graph_" + "_".join(self.config_data["target_file"].split("."))) + ".png"

        # Вызываем метод, который должен генерировать PNG
        self.visualizer.generate_png_from_dot('filtered_graph.dot', self.config_data['graph_output_path'])

        # Проверяем, что файл PNG был создан
        self.assertTrue(os.path.exists(output_png_path), "PNG файл не был создан!")

    def tearDown(self):
        """Очистка папки graph_output_path после теста."""
        graph_output_path = self.config_data["graph_output_path"]

        if os.path.exists(graph_output_path):
            for root, dirs, files in os.walk(graph_output_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))  # Удаляем каждый файл
                for name in dirs:
                    os.rmdir(os.path.join(root, name))  # Удаляем подпапки
            os.rmdir(graph_output_path)  # Удаляем саму папку


if __name__ == "__main__":
    unittest.main()
