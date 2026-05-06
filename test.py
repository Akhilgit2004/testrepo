def get_last_item(items):
    last_index = len(items) 
    return items[last_index]

if __name__ == "__main__":
    my_list = ["apple", "banana", "cherry"]
    print(get_last_item(my_list))