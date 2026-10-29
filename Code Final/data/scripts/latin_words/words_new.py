'''
Class to interface with Whitaker's Words program.
'''

import os
import pexpect
import re
from pprint import pprint
import unicodedata


class Words:
    def __init__(self):
        # CURRENT WORKING DIR MUST BE DIR THAT CONTAINS FILES
        # FOR INFLECTIONS, DICTIONARY, ADDONS AND UNIQUES
        os.chdir('/home/amys/words/whitakers-words')
        self._start_child()

    def _start_child(self):
        '''Start (or restart) the Whitaker's Words child process.'''

        # start the program
        self.child = pexpect.spawn('/home/amys/words/whitakers-words/bin/words')

        # wait for input
        self.child.expect('=>')

        # setting TRIM_OUTPUT as no to receive less probable forms too
        self.child.sendline('#') # Input # to change parameters and mode of the program
        self.child.expect('=>')
        self.child.sendline('n')
        self.child.expect('=>')
        self.child.sendline(' ')

        # wait for input
        self.child.expect('=>')

    def _flush_to_prompt(self):
        '''
        Consume any pending MORE pages and stale output until we reach a clean => prompt.
        Used to recover the child process after a TIMEOUT.
        '''

        for _ in range(50):  # safety cap on pages
            try:
                idx = self.child.expect(
                    [r'(?m)^[\r\n]*=> ?$', r'MORE - hit RETURN/ENTER to continue'],
                    timeout=5
                )
                if idx == 0:
                    return  # reached clean prompt
                # idx == 1: another MORE page — send blank to continue
                self.child.sendline('')
            except (pexpect.EOF, pexpect.TIMEOUT):
                return  # nothing more to drain

    # def analyze(self, word: str, _retried: bool = False):
    #     '''
    #     Analyze a word and return its morphological information.
        
    #     Auto-restarts the child process once if an EOF is encountered.
    #     '''

    #     # remove any accents
    #     word = self.remove_accents(word)
        
    #     try:
    #         # send word to program
    #         self.child.sendline(word)

    #         # read output until next prompt
    #         idx = self.child.expect([r'(?m)^[\r\n]*=> ?$', r'MORE - hit RETURN/ENTER to continue'])
    #         if idx == 1:
    #             self.child.sendline('')
    #             # self.child.expect(r'(?m)^[\r\n]*=> ?$')

    #         # return text before the prompt after it has been parsed
    #         return self.parse_output(self.child.before.strip())

    #     except pexpect.EOF:
    #         if _retried:
    #             # Already retried once - give up for this word
    #             raise
    #         # Child process died; restart it and try once more
    #         try:
    #             self.child.close()
    #         except Exception:
    #             pass
    #         self._start_child()
    #         return self.analyze(word, _retried=True)
        
    def analyze(self, word: str, _retried: bool = False):
        '''
        Analyze a word and return its morphological information.

        - Loops through any number of MORE pages to collect full output.
        - On EOF: restarts the child process and retries once.
        - On TIMEOUT: flushes stale output back to a clean prompt and retries once.
        '''

        # remove any accents
        word = self.remove_accents(word)

        try:
            # send word to program
            self.child.sendline(word)

            # collect output, paging through as many MORE prompts as needed
            output_chunks = []
            while True:
                idx = self.child.expect(
                    [r'(?m)^[\r\n]*=> ?$', r'MORE - hit RETURN/ENTER to continue']
                )
                output_chunks.append(self.child.before)
                if idx == 0:
                    break           # reached the final => prompt
                # idx == 1: MORE page — send blank to get next page
                self.child.sendline('')

            combined = b''.join(output_chunks).strip()
            return self.parse_output(combined)

        except pexpect.EOF:
            if _retried:
                raise
            try:
                self.child.close()
            except Exception:
                pass
            self._start_child()
            return self.analyze(word, _retried=True)

        except pexpect.TIMEOUT:
            if _retried:
                raise
            # Child is alive but stuck (e.g. on an unread MORE page).
            # Drain back to a clean prompt, then retry.
            self._flush_to_prompt()
            return self.analyze(word, _retried=True)



    def parse_output(self, output: bytes):
        '''Parse the output from Words program into structured data.'''

        if not output or not output.strip():
            return []
        
        # output in byte str -> use .decode('ASCII') to convert to str
        output_str = output.decode('ASCII')

        # all entries related to the given word
        # the same inflected word can come from multiple different lemmas
        # separate entries for each
        entries = [] 

        current_entry = None # current lemma being processed
        current_forms = [] # all the inflected forms for that lemma
        seen_lemma = False

        lines = [line.strip() for line in output_str.strip().splitlines() if line.strip()]
        if not lines:
            return []

        # first line is the input word
        inflection = lines[0].lower() 

        # print(inflection) # debug

        # for inflection info line
        inflection_pattern = re.compile(
            r'^([A-Za-z\.\-]+)\s+'          # word form (letters, dots, hyphens)
            r'([A-Za-z]+)\s+'               # POS (N, V, ADJ, ADV, etc.)
            r'([\d ]+)\s+'                  # numbers (declension/conjugation)
            r'([A-Za-z ]+?)'                # grammatical info (case, number, gender, etc.)
            r'(?:\s{2,}(.+))?$',            # optional trailing comment (e.g. "uncommon") FIX SPACE ISSUE
        )
        verb_pattern = re.compile(
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Za-z]+)\s+'               # pos
            r'([\d ]+)\s+'                  # conjugation numbers
            r'([A-Za-z]+)\s+'               # tense
            r'(ACTIVE|PASSIVE)?\s*'         # voice (may be excluded)
            r'([A-Za-z]+)\s+'               # mood
            r'([\d])\s+'                    # person
            r'([SP])'                       # number
            r'(?:\s{2,}(.+))?$',            # optional comment
        )
        noun_pattern = re.compile(
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Z])\s+'                   # pos
            r'([\d ]+)\s+'                  # declension numbers
            r'([A-Z]+)\s+'                  # case
            r'([SP])\s+'                    # number 
            r'([A-Z])'                      # gender 
            r'(?:\s{2,}(.+))?$'             # optional comment
        )
        adj_pattern = re.compile(
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Z]+)\s+'                  # pos
            r'([\d ]+)\s+'                  # declension numbers
            r'([A-Z]+)\s+'                  # case
            r'([SP])\s+'                    # number 
            r'([A-Z])\s+'                   # gender 
            r'([A-Z]+)'                     # degree (positive, superlative, etc)
            r'(?:\s{2,}(.+))?$'             # optional comment
        )
        adv_pattern = re.compile( # NEED TO TEST
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Z]+)\s+'                  # pos
            r'([A-Z]+)'                     # degree
            r'(?:\s{2,}(.+))?$'             # optional comment
        )
        ptcp_pattern = re.compile( # participle 
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Z]+)\s+'                  # pos
            r'([\d ]+)\s+'                  # conjugation numbers
            r'([A-Z]+)\s+'                  # case
            r'([SP])\s+'                    # number
            r'([A-Z])\s+'                   # gender
            r'([A-Z]+)\s+'                  # tense
            r'([A-Z]+)\s+'                  # voice
            r'([A-Z]+)'                     # participle type
            r'(?:\s{2,}(.+))?$'             # optional comment
        ) 
        # pron_pattern = re.compile( # pronoun - not finished
        #     r'^([A-Za-z\.\-]+)\s+'          # word
        #     r'([A-Z]+)\s+'                  # pos

        #     r'(?:\s{2,}(.+))?$'             # optional comment
        # )
        # prep_pattern = re.compile(

        # ) # preposition
        # num_pattern = re.compile(

        # )
        supine_pattern = re.compile(
            r'^([A-Za-z\.\-]+)\s+'          # word
            r'([A-Z]+)\s+'                  # pos
            r'([\d ]+)\s+'                  # conjugation numbers
            r'([A-Z]+)\s+'                  # case 
            r'([SP])\s+'                    # number 
            r'([A-Z])'                      # gender 
            r'(?:\s{2,}(.+))?$'             # optional comment
        )


        # lemma_pattern = re.compile(
        #     r'^([A-Za-z, \-\+]+)\s+'        # lemma(s)
        #     r'([A-Za-z]+)\s+'               # POS (N, V, ADJ, etc.)
        #     r'\(([^)]+)\)\s+'               # parentheses content (declension/conjugation)
        #     r'([A-Za-z]+)\s+'               # gender (M, F, N)
        #     r'\[([A-Z]+)\]'                 # code like [XWXAO]
        #     r'(?:\s{2,}(.+))?$',            # optional trailing comment ("Pliny", "uncommon")
        # )

        lemma_pattern = re.compile(
            r'^'                                        # start of line
            r'([A-Za-z0-9,\s\-\+\']+?)'                 # (1) lemma text (non-greedy)
            r'\s+'                                      # whitespace
            r'([A-Za-z]+)'                              # (2) POS (N, V, ADJ, etc.)
            r'(?:\s+\(([^)]+)\)(?:\s+([A-Za-z]+))?)?'   # (3) optional parentheses, (4) optional gender
            r'\s+\[([A-Z]+)\]'                          # (5) Whitaker code in brackets
            r'(?:\s{2,}(.+))?'                          # (6) optional trailing comment like "Pliny" or "uncommon"
            r'$'                                        # end of line
        )

        # parse lines
        for i in range(1, len(lines)):
            line = lines[i]

            inf_match = inflection_pattern.match(line)
            lemma_match = lemma_pattern.match(line)

            if inf_match:
                # New entry starts if we already had a lemma before
                if current_entry and seen_lemma:
                    entries.append(current_entry)
                    current_entry = None
                    current_forms = []
                    seen_lemma = False

                form, pos, _, _, _ = inf_match.groups()

                # initialise all variables
                conj = None
                decl = None
                case = None
                number = None
                gender = None
                tense = None
                voice = None
                mood = None
                person = None
                degree = None
                ptcp_type = None
                comment = None

                # continue parsing rest of tags in line based on POS
                if pos == 'V':
                    verb_match = verb_pattern.match(line)
                    if verb_match:
                        form, pos, conj, tense, voice, mood, person, number, comment = verb_match.groups()
                        decl = None
                        gender = None
                        case = None
                        degree = None
                        ptcp_type = None
                elif pos == 'N':
                    noun_match = noun_pattern.match(line)
                    if noun_match:
                        form, pos, decl, case, number, gender, comment = noun_match.groups()
                        conj = None
                        tense = None
                        voice = None
                        mood = None
                        person = None
                        degree = None
                        ptcp_type = None
                elif pos == 'ADJ':
                    adj_match = adj_pattern.match(line)
                    if adj_match:
                        form, pos, decl, case, number, gender, degree, comment = adj_match.groups()
                        conj = None
                        tense = None
                        voice = None
                        mood = None
                        person = None
                        ptcp_type = None
                elif pos == 'ADV':
                    adv_match = adv_pattern.match(line)
                    if adv_match:
                        form, pos, degree, comment = adv_match.groups()
                        decl = None
                        case = None
                        number = None
                        gender = None
                        conj = None
                        tense = None
                        voice = None
                        mood = None
                        person = None
                        ptcp_type = None
                elif pos == 'VPAR':
                    ptcp_match = ptcp_pattern.match(line)
                    if ptcp_match:
                        form, pos, conj, case, number, gender, tense, voice, ptcp_type, comment = ptcp_match.groups()
                        decl = None
                        degree = None
                        mood = None
                        person = None
                # elif pos == 'PRON':
                #     pass
                # elif pos == 'PREP':
                #     pass
                # elif pos == 'NUM':
                #     pass
                elif pos == 'SUPINE':
                    sup_match = supine_pattern.match(line)
                    if sup_match:
                        form, pos, conj, case, number, gender, comment = sup_match.groups()
                        decl = None
                        degree = None
                        mood = None
                        person = None
                        tense = None
                        voice = None
                        ptcp_type = None
                # else:
                #     pass
               
                entry = {
                    'form': form,
                    'part_of_speech': pos,
                    'conjugation': conj.split()[0] if conj else None,
                    'declension': decl.split()[0] if decl else None,
                    'gender': gender,
                    'case': case,
                    'number': number,
                    'tense': tense,
                    'voice': voice,
                    'mood': mood,
                    'person': person,
                    'degree': degree,
                    'participle_type': ptcp_type,
                    'comment': comment
                }
                current_forms.append(entry)

            elif lemma_match:
                lemma_text, _, _, _, _, _ = lemma_match.groups()
                current_entry = {
                    'lemma': lemma_text.strip(),
                    'forms': current_forms,
                }
                seen_lemma = True
        
        # catch last entry
        if current_entry:
            # current_entry['forms'] = current_forms
            entries.append(current_entry)

        return entries
        
    def remove_accents(self, text: str) -> str:
        '''Remove accents and diacritics from a word.'''
        text = unicodedata.normalize('NFD', text)
        text = text.encode('ascii', 'ignore') # discard non ascii characters
        text = text.decode('utf-8')
        return text

    # def close(self):
    #     # exit program - two empty lines
    #     self.child.sendline('')
    #     self.child.sendline('')
    #     self.child.expect(pexpect.EOF)
    #     self.child.close()

    def close(self):
        # exit program - two empty lines
        if hasattr(self, "child") and self.child is not None:
            if self.child.isalive():
                self.child.sendline('')
                self.child.sendline('')
                self.child.expect(pexpect.EOF, timeout=5)
            self.child.close()



