import os
import json
from graphviz import Source
import zlib
from datetime import datetime


class DependencyVisualizer:
    def __init__(self, config_path):
        # Загружаем конфигурацию из файла
        with open(config_path, 'r') as f:
            self.config = json.load(f)

    def parse_object(self, object_hash, description=None, author_data=None):
        """
        Извлечь информацию из git-объекта по его хэшу.
        """
        object_path = os.path.join(self.config['repo_path'], '.git', 'objects', object_hash[:2], object_hash[2:])

        if not os.path.exists(object_path):
            print(f"Warning: Object {object_hash} not found. Skipping.")
            return {'label': f'[missing] {object_hash}', 'children': []}

        with (open(object_path, 'rb') as file):
            raw_object_content = zlib.decompress(file.read())
            header, raw_object_body = raw_object_content.split(b'\x00', maxsplit=1)
            object_type, content_size = header.decode().split(' ')

            object_dict = {}

            if object_type == 'commit':
                commit_data = self.parse_commit(raw_object_body)
                author_data = {
                    'author_name': commit_data["author_name"],
                    'author_date': commit_data["author_date"]
                }
                object_dict['label'] = (
                    f'[commit] {object_hash[:6]}\n'
                    f'Author: {author_data["author_name"]}\n'
                    f'Date: {author_data["author_date"]}'
                )
                object_dict['children'] = [self.parse_object(commit_data['tree'])] + [self.parse_object(parent) for
                                                                                      parent in commit_data['parents']]
                # object_dict['children'] = [
                #     self.parse_object(commit_data['tree'], author_data=author_data)
                # ] + [self.parse_object(parent, author_data=author_data) for parent in commit_data['parents']]

            elif object_type == 'tree':
                object_dict['label'] = (
                    f'[tree] {object_hash[:6]}'
                    # f'\nAuthor: {author_data["author_name"] if author_data else "Unknown"}\n'
                    # f'Date: {author_data["author_date"] if author_data else "Unknown"}'
                )
                object_dict['children'] = self.parse_tree(raw_object_body, author_data)

            elif object_type == 'blob':
                object_dict['label'] = (
                    f'[blob] {object_hash[:6]}'
                    # f'\nAuthor: {author_data["author_name"] if author_data else "Unknown"}\n'
                    # f'Date: {author_data["author_date"] if author_data else "Unknown"}'
                )
                object_dict['children'] = []

            if description is not None:
                object_dict['label'] += f'\n{description}'

            return object_dict

    def parse_tree(self, raw_content, author_data):
        """
        Парсим git-объект дерева.
        """
        children = []
        rest = raw_content
        while rest:
            mode, rest = rest.split(b' ', maxsplit=1)
            name, rest = rest.split(b'\x00', maxsplit=1)
            sha1, rest = rest[:20].hex(), rest[20:]
            children.append(self.parse_object(sha1, description=name.decode(), author_data=author_data))
        return children

    def parse_commit(self, raw_content):
        """
        Парсим git-объект коммита.
        """
        content = raw_content.decode()
        content_lines = content.split('\n')

        commit_data = {'parents': [], 'tree': content_lines[0].split()[1]}

        content_lines = content_lines[1:]

        while content_lines[0].startswith('parent'):
            commit_data['parents'].append(content_lines[0].split()[1])
            content_lines = content_lines[1:]

        for line in content_lines:
            if line.startswith('author'):
                author_data = line[len('author '):].split()
                author_name = ' '.join(author_data[:-3])
                timestamp = int(author_data[-2])
                commit_data['author_name'] = author_name
                commit_data['author_date'] = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            elif line.startswith('committer'):
                break

        return commit_data

    def get_last_commit(self):
        """Получить хэш для последнего коммита в ветке"""
        head_path = os.path.join(self.config['repo_path'], '.git', 'refs', 'heads', self.config['branch'])
        with open(head_path, 'r') as file:
            return file.read().strip()

    def add_one_to_parents_if_target_found(self, tree, target_file):
        """Рекурсивно добавлять '1' в начало label родительским узлам, если найден target_file в label одного из детей."""

        def recursive_add(node):  # , is_tree=False):
            # Переменная для проверки, был ли найден target_file у этого узла или у его детей
            found_target = False

            # Если узел типа [blob], проверяем, содержит ли его label target_file
            if '[blob]' in node['label']:
                # if is_tree:
                #     if not node['label'].startswith('1'):
                #         node['label'] = '1' + node['label']
                #         return False
                if target_file in node['label']:
                    # Если находим target_file, ставим '1' в начало label
                    if not node['label'].startswith('1'):
                        node['label'] = '1' + node['label']
                    found_target = True

            # Рекурсивно проверяем всех детей этого узла
            for child in node['children']:
                # Если у дочернего узла есть target_file или он обновил свой label, возвращаем True
                if recursive_add(child):
                    found_target = True

            # Если хотя бы один из детей или сам объект содержит target_file, ставим '1' в label родителя
            if found_target and not node['label'].startswith('1'):
                node['label'] = '1' + node['label']

            # if (found_target or is_tree) and "[tree]" in node['label']:
            #     for child in node['children']:
            #         if not child['label'].startswith('1'):
            #             child['label'] = '1' + child['label']
            #         recursive_add(child, True)

            if "[commit]" in node["label"]:
                found_target = False

            return found_target

        # Запускаем рекурсию от корня дерева
        recursive_add(tree)

    def generate_dot_filtered(self, target_file, filename):
        """Создать DOT-файл для графа зависимостей, учитывая target_file."""

        last_commit = self.get_last_commit()
        tree = self.parse_object(last_commit)

        # Добавляем единицу в label для всех объектов blob, содержащих target_file, и их родителям
        self.add_one_to_parents_if_target_found(tree, target_file)

        # Далее нужно вывести дерево в формат DOT
        with open(filename, 'w') as file:
            file.write('digraph G {\n')

            def recursive_write(file, tree):
                label = tree['label']
                current_graph = []
                if label[0] == "1":
                    for child in tree['children']:
                        if child["label"][0] == "1":
                            current_graph += [f'    "{label[1:]}" -> "{child["label"][1:]}"\n'] + recursive_write(file,
                                                                                                                  child)
                return current_graph

            # Печать дерева в DOT файл
            graph = recursive_write(file, tree)
            file.write("".join(list(set(graph))))

            file.write('}')

    def generate_png_from_dot(self, dot_file_path, output_png_path):
        self.generate_dot_filtered(self.config["target_file"], 'filtered_graph.dot')

        try:
            # Проверяем, существует ли папка для сохранения файла
            output_dir = os.path.dirname(output_png_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)  # Если папка не существует, создаем её

            # Открываем dot-файл
            with open(dot_file_path, 'r') as file:
                dot_content = file.read()

            # Создаем объект Source из содержимого dot-файла
            source = Source(dot_content)

            # Генерируем PNG файл
            source.render(output_png_path + "/graph_" + "_".join(self.config["target_file"].split(".")), format='png',
                          cleanup=True)
            print(
                f"PNG файл успешно создан: {output_png_path + '/graph_' + '_'.join(self.config['target_file'].split('.'))}")
            os.remove(dot_file_path)

        except Exception as e:
            print(f"Ошибка при создании PNG файла: {e}")


if __name__ == "__main__":
    visualizer = DependencyVisualizer('config.json')
    visualizer.generate_png_from_dot('filtered_graph.dot', visualizer.config["graph_output_path"] +
                                     "/" + visualizer.config["repo_path"].split("/")[-1] +
                                     "/" + visualizer.config["branch"])
