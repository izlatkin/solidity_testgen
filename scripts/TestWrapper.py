import os.path


def is_fun_supported(fun_signature):
    # currently only int formate is supported
    for f in fun_signature:
        # if f != "uint":
        if "uint" not in f:
            return False
    return True


class TestWrapper:

    def __init__(self, testgen_file, signature):
        self.testgen_file = testgen_file
        self.signature = signature

    def read(self, file):
        f = open(file, "r")
        inside_test = False
        raw_tests = []
        a_test = []
        for line in f.readlines():
            if "END TEST" in line:
                inside_test = False
                if a_test:
                    raw_tests.append(a_test)
                a_test = []
            if inside_test:
                if line:
                    a_test.append(line.strip())
            if "NEW TEST" in line:
                inside_test = True
        return raw_tests

    def is_int(self, string):
        try:
            string_integer = int(string)
            return 1
        except ValueError:
            return 0

    def get_values(cls, raw_list):
        order = []
        test = {}
        for item in raw_list:
            tokens = item.strip().split()
            if len(tokens) < 2:
                print("Error: check!")
                continue
            chc_name = tokens[0]
            var_value = tokens[2][1:-1]
            tmp = var_value.split('=')
            var = int(tmp[0][len("_tg_"):])
            value = -1
            if "array" in tmp[1] or "store" in tmp[1]:
                continue
            else:
                value = int(tmp[1])
            if "contract" in chc_name:
                if "contract" in test:
                    if var in test["contract"]:
                        test["contract"][var].append(value)
                    else:
                        test["contract"][var] = [value]
                else:
                    tmp_dict = {}
                    tmp_dict[var] = [value]
                    test["contract"] = tmp_dict
                if "contract" not in order:
                    order.append("contract")
            if "block" in chc_name and "function" in chc_name and "summary" not in chc_name and "return" not in chc_name:
                start = chc_name.index("_function_")
                end = chc_name.index("__")
                if start < 0 or end < 0:
                    print("Error2: check!")
                    continue
                function_name = chc_name[start + len("_function_"): end]
                if function_name not in order:
                    order.append(function_name)
                if function_name in test:
                    if var in test[function_name]:
                        test[function_name][var].append(value)
                    else:
                        test[function_name][var] = [value]
                else:
                    tmp_dict = {}
                    tmp_dict[var] = [value]
                    test[function_name] = tmp_dict

        test["order"] = order
        return test

    def wrap(self, log_file, signature):
        raw_tests = self.read(log_file)
        clean_tests = [self.get_values(test) for test in raw_tests]
        return clean_tests

    def wrap(self):
        if os.path.isfile(self.testgen_file):
            raw_tests = self.read(self.testgen_file)
            # clean_tests = [self.get_values(test) for test in raw_tests]
            return raw_tests
        else:
            return False

    def remove_duplicates(self, tests):
        out = []
        uniq = set()
        for t in tests:
            if str(t) not in uniq:
                uniq.add(str(t))
                out.append(t)
        return out

    def generate_sol_test(self, clean_tests, file_name):
        name_wo_extension = os.path.splitext(file_name)[0]
        test_name = name_wo_extension + ".t.sol"
        # test_file_full_path = "/Users/ilyazlatkin/CLionProjects/blockchain_exp/hello_foundry/test/" + test_name
        test_file_full_path = str(os.path.dirname(os.path.realpath(__file__))) + "/../test/" + test_name
        test_file = open(test_file_full_path, 'w')

        # generate header/import part
        header = ["//Generated Test by TG\n", "//{}\n".format(str(self.signature)),
                  #"pragma solidity ^0.8.13;\n\n",
                  "import \"forge-std/Test.sol\";\n",
                  "import \"../src/{}.sol\";\n\n".format(name_wo_extension),
                  f'contract {name_wo_extension}_Test is Test' + ' {\n']

        fields = []
        setUp = []
        test_body = []
        for index, test in enumerate(clean_tests):

            # contracts declaration
            type = self.signature[0][0][1]
            contract_names = [self.signature[i][0][0] for i,_ in enumerate(self.signature)]
            #contract_var = "c" + str(index)
            contract_vars = [c_name.lower() + str(index) for c_name in contract_names]

            if type in ['contract', 'library']:  # skip interphases
                for i, c_name in enumerate(contract_names):
                    fields.append("\t{} {};\n".format(c_name, contract_vars[i]))

            # generate setUp function
            if type in ['contract', 'library']:  # skip interphases
                # ToDo: add check if constructor signature
                init_part_of_test = [tt for tt in test if "contract_" in tt]
                for tt in init_part_of_test:
                    for i, c_name in enumerate(contract_names):
                        if 'contract_{}'.format(c_name) not in tt:
                            continue
                        if tt == 'contract_{}()'.format(c_name) or 'contract' not in test[0]:
                            constructor_args_values = '()'
                        else:
                            tmp = tt
                            start = tmp.index('(')
                            end = tmp.index(')')
                            constructor_args_values = tmp[start:end + 1]
                        tt.split('_')
                        setUp.append("\t\t{} = new {}{};\n".format(contract_vars[i], c_name, constructor_args_values))

                # generate Tests : one test for each function for each contract
                # find fun_signature
                funcs_calls = [tt for tt in test if "contract_" not in tt]
                test_body.append(f'\tfunction test_{name_wo_extension}_{index}() public ' + '{\n')
                for calls in funcs_calls:
                    fun_signature = []
                    c_index = 0
                    f_name_tmp = calls[:calls.index('(')]
                    for j, sg in enumerate(self.signature):
                        for y in [tmp[0] for tmp in sg]:
                            if f_name_tmp == y:
                                c_index = j
                                break
                    for s in self.signature[c_index][1:]:  # ToDo add mutliple contracts
                        fun_signature = s
                    if not fun_signature:  # "function not found case"
                        continue
                    # check = is_fun_supported(fun_signature[1:])
                    # if check:
                    f_name = calls.split('__')[0]
                    ucall = f_name + calls[calls.index('('):]
                    test_body.append("\t\t{}.{}; //{}\n".format(contract_vars[c_index], ucall, calls))
                test_body.append("\t\tassertTrue(true);\n\t}\n")

        out = header + fields + ["\tfunction setUp() public {\n"] + setUp + ["\t}\n"] \
              + test_body + ["}\n"]

        # for o in out:
        #     print(o)
        test_file.writelines(out)
        test_file.close()


if __name__ == '__main__':
    tw = TestWrapper("../sandbox/testgen.txt",
                     [[['C', 'contract'], ['test', 'uint256', 'a', 'uint256', 'b']]])  # nested_if
    tw = TestWrapper("../sandbox/testgen.txt",
                     [[['C', 'contract', 'uint256', 'b'], ['f', 'uint256', 'x'], ['set_max', 'uint256', 'x', 'uint256', 'y']]])  # contract_1.sol
    tw = TestWrapper("../sandbox/testgen.txt",
                     [[['A', 'contract', 'uint256', 'a'], ['f']],
                      [['B', 'contract', 'uint256', 'b'], ['f'], ['g']]])  # contract_3.sol
    # tw = TestWrapper("../sandbox/testgen.txt", [[['C', 'contract'], ['simple_if', 'uint256']]])  # simple_if
    [print(e) for e in tw.wrap()]
    # cleaned = tw.remove_duplicates(tw.wrap())
    tw.generate_sol_test(tw.wrap(), "constructor_3")
    # [print(e) for e in cleaned]
    # python script to generate Solidity Tests from Raw log and signature of Sol file
