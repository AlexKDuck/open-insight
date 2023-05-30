import nltk
import tkinter
import PyPDF2
from pymongo import MongoClient
import logging
import re
import json
from objdict import ObjDict


# Download necessary NLTK packages
nltk.download('punkt')
#nltk.download('averaged_perceptron_tagger')

# Connect to MongoDB
#client = MongoClient('mongodb://localhost:27017')
client = MongoClient('mongodb://penguin:27017')
db = client['santa_monica_data']
collection = db['parsed_minutes_pdfs']

return_object = ObjDict()


#grammar = """
#    Chunk: {<.*>+}
#    }<CD>{"""
#    }<LS>{"""
#    }<CD>{"""
#chunk_parser = nltk.RegexpParser(grammar)


# Function to parse PDF and extract text
def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        num_pages = len(pdf_reader.pages)

        text = ''
        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        return text


def convert_month_text_to_ordinal(text):
    if text=="JAN": return 1
    elif text=="FEB": return 2
    elif text=="MAR": return 3
    elif text=="APR": return 4
    elif text=="MAY": return 5
    elif text=="JUN": return 6
    elif text=="JUL": return 7
    elif text=="AUG": return 8
    elif text=="SEP": return 9
    elif text=="OCT": return 10
    elif text=="NOV": return 11
    elif text=="DEC": return 12
    else: return -1

# Function to tokenize and tag the text using NLTK
def tokenize_text(text):
    sentences = nltk.sent_tokenize(text)
#    tokenized_sentences = [nltk.word_tokenize(sentence) for sentence in sentences]
#    tagged_sentences = [nltk.pos_tag(tokens) for tokens in tokenized_sentences]
    return sentences

def extract_ordinances_from_minutes(sentences):
    ordinances=False
    ordinance_text=[]
    for sentence in sentences:
        sentence = remove_noise(sentence)
        if(ordinances):
            end_flag_position = get_end_ordinance_flag_position(sentence)
            if end_flag_position >= 0:
                ordinances=False
                ordinance_text.append(sentence[0:end_flag_position])
            else:
                ordinance_text.append(sentence)
        else:
            ordinance_text_position = sentence.find("ORDINANCES")
            if ordinance_text_position >= 0:
                new_var = sentence[ordinance_text_position:]
                ordinance_text.append(new_var)
#        if sentence.find("10.A.") >= 0:
                ordinances=True
    return ''.join(ordinance_text)

def remove_noise(sentence):
    sentence=re.sub('\n','',sentence).strip()
    docusign_envelope_id = sentence.find('DocuSign Envelope ID')
    if docusign_envelope_id >= 0:
        sentence = ''.join([sentence[0:docusign_envelope_id], sentence[find_docusign_end(sentence, docusign_envelope_id):]])
    return sentence

def find_docusign_end(sentence, start):
    current = start + 61 # seems to be magic number
    while current < len(sentence):
        new_var = sentence[current]
        if new_var >= '0' and sentence[current] <= '9':
            new_var1 = sentence[current+1]
            if new_var1 >= '0' and sentence[current+1] <= '9':
                new_var2 = sentence[current+2]
                if new_var2 >= '0' and sentence[current+2] <= '9':
                    new_var3 = sentence[current+3]
                    if new_var3 >= '0' and sentence[current+3] <= '9':
                        return current+4
                    else:
                        current+=4
                else:
                    current+=3
            else:
                current+=2
        else:
            current+=1



def get_end_ordinance_flag_position(sentence):
    flag1 = sentence.find("CONTINUE MEETING")
    if flag1 >= 0:
        return flag1
    else:
        flag2 = sentence.find("STAFF ADMINISTRATIVE ITEMS")
        if flag2 >= 0:
            return flag2
        else:
            flag3 = sentence.find("AGENDA MANAGEMENT")
            if flag3 >= 0:
                return flag3
            else:
                flag4 = sentence.find("COUNCILMEMBER DISCUSSION ITEMS")
                return flag4
            
def extract_ordinance_json_from_text(ordinances_text):
    ordinances = []
    ordinance_index = 0
    current_text = ordinances_text[ordinances_text.find(':')+1:].strip()
    while True:
        ordinance_object = ObjDict()
        ordinance_number = ''.join(['10.',chr(ord('A')+ordinance_index),'.'])
        ordinance_object.meetingnoteslineitem=ordinance_number
        ordinance_number_index = current_text.find(ordinance_number)
        ordinance_subject = current_text[:ordinance_number_index].strip()
        ordinance_object.subject = ordinance_subject
        end_ordinance_title_index = current_text.find(', was presented')
        ordinance_object.title = current_text[ordinance_number_index+5:end_ordinance_title_index].strip()
        recommended_action_index = current_text.find('Recommended Action')
        current_text = current_text[recommended_action_index+len('Recommended Action'):].strip()
        next_colon_index = current_text.find(':')
        next_period_index = current_text.find('.')
        if next_colon_index>=0 and next_colon_index < next_period_index:
            recommended_action_text = current_text.strip()
            ordinance_object.Recommended_Actions=[]
            ordinance_object.Recommended_Actions.append(recommended_action_text)
        else:
            ordinance_object.Recommended_Actions = current_text[:next_period_index+1].strip()
            current_text = current_text[next_period_index+1:]
        ayes_index = current_text.find('AYES')
#        ordinance_object.other_text = current_text[:ayes_index]
        current_text = current_text[ayes_index:].strip()
        noes_index = current_text.find('NOES')
        absent_index = current_text.find('ABSENT')
        ayes_text = current_text[5:noes_index].strip()
        noes_text = current_text[noes_index+5:absent_index].strip()
        current_text = current_text[absent_index:].strip()
        end_of_absent_index = get_end_of_absent_index(current_text)
        absent_text = current_text[len('ABSENT:'):end_of_absent_index].strip()
        current_text = current_text[end_of_absent_index:].strip()
        ordinance_object.AYES = ayes_text
        ordinance_object.NOES = noes_text
        ordinance_object.ABSENT = absent_text
        ordinances.append(ordinance_object)
        ordinance_index+=1
        if len(current_text) == 0:
            break
    return ordinances


def get_end_of_absent_index(text):
    index = len('ABSENT:')
    while True:
        if text[index:].startswith('None'):
            return index+len('None')
        else:
            index+=1
    
def extract_date_from_minutes(sentences):
    date_finder = "CITY COUNCIL MINUTES"
    date_index = sentences[0].find(date_finder)
    text_with_date = sentences[0][date_index+len(date_finder):date_index+100].lstrip()
    tokenized_text_with_date = nltk.word_tokenize(text_with_date)
    if tokenized_text_with_date[2]==',':
        date = int(tokenized_text_with_date[3])*10000+int(tokenized_text_with_date[1])
    else:
        date = int(tokenized_text_with_date[4])*10000+int(tokenized_text_with_date[1])*10+int(tokenized_text_with_date[2])
    month_text = tokenized_text_with_date[0][0:3]
    date+= 100*convert_month_text_to_ordinal(month_text)
    return date

# Example usage
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230425.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230321.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230321_spe.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230314.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230311.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230228.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230222.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230214.pdf'  # Replace with your PDF file path
#pdf_file = 'sampledata/SantaMonica/Minutes/m20230124.pdf'  # Replace with your PDF file path
pdf_file = 'sampledata/SantaMonica/Minutes/m20230110.pdf'  # Replace with your PDF file path

minutes_object = ObjDict()
# Parse PDF and extract text
minutes_text = extract_text_from_pdf(pdf_file)

# Tokenize and tag the text using NLTK
minutes_sentences = tokenize_text(minutes_text)
meeting_date = extract_date_from_minutes(minutes_sentences)
minutes_object.date = str(meeting_date)
#logging.error("Date: "+str(meeting_date))

ordinances_text = extract_ordinances_from_minutes(minutes_sentences)
minutes_object.ordinances = extract_ordinance_json_from_text(ordinances_text)
#minutes_object.ordinances_text = ordinances_text


#return_object.minutes = [minutes_object]
 
# Insert parsed data into MongoDB
return_json = minutes_object.dumps()
#print("Ordinances JSON: "+str(return_json))
print(json.dumps(json.loads(return_json), indent=2))
collection.insert_one({"minutes": minutes_object, 'json':return_json,'meeting_date': meeting_date, 'meeting_ordinances_text': ordinances_text, 'meeting_minutes_text': minutes_text})

# Close the MongoDB connection
client.close()