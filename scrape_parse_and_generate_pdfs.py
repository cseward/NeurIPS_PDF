from bs4 import BeautifulSoup
import requests
import re
import codecs
import pickle
import subprocess

def clean_string(input_string):
  input_string = re.sub('\n', ' ', input_string)
  input_string = re.sub(' +', ' ', input_string)
  input_string = re.sub('#', '\\#', input_string)
  input_string = re.sub('&', '\\&', input_string)
  input_string = re.sub('\xb7', '$\\cdot$', input_string)
  return input_string
  
def make_infodict(div):
  '''
  Create a dictionary with all the information on one session
  '''
  info_dict = {'time_and_location' : None, "type" : None, "title": None, "presenter": None, "session": ""}
  for subdiv in div.find_all("div"):
    try:
      if u"maincardType" in subdiv["class"]:
        if info_dict["type"] == None:
          info_dict["type"] = clean_string(subdiv.text)
        else:
          info_dict["session"] = clean_string(subdiv.text).encode('ascii','ignore')
      if u"maincardHeader" in subdiv["class"] and u"maincardType" not in subdiv["class"]:
        info_dict["time_and_location"] = clean_string(subdiv.text).encode('ascii','ignore')
      if u"maincardBody" in subdiv["class"]:
        info_dict["title"] = clean_string(subdiv.text)
      if u"maincardFooter" in subdiv["class"]:
        info_dict["presenter"] = clean_string(subdiv.text).encode('ascii','replace')
    except KeyError:
      pass  
  for key in info_dict.keys():
    if info_dict[key] == None:
      raise ValueError("no value for " + key + "in " + str(div))
  return info_dict

def scrape_one_day(page_link):
  '''
  scrape all the information of one day, returning a dictionary with 
  '''
  page_response = requests.get(page_link, timeout=5)
  page_content = BeautifulSoup(page_response.content, "html.parser")
  
  all_infodicts = []
  
  all_div = page_content.find_all("div")
  for div in all_div:
    try:
      if u"maincard" in div["class"]:
        all_infodicts.append(make_infodict(div))
    except KeyError:
      pass
  return all_infodicts

def crosslink_posters_and_talks(all_infodicts):
  '''
  add poster information for each talk and talk information for each poster
  '''
  title_to_talk = {}
  title_to_poster = {}
  
  for i,infodict in enumerate(all_infodicts):
    title = infodict["title"]
    if infodict["type"] == u"Spotlight" or infodict["type"] == u"Oral":
      title_to_talk[title] = i
    if infodict["type"] == u"Poster":
      title_to_poster[title] = i
  
  for i in range(len(all_infodicts)):
    title = all_infodicts[i]["title"]
    if all_infodicts[i]["type"] == u"Spotlight" or all_infodicts[i]["type"] == u"Oral":
      if title in title_to_poster:
        all_infodicts[i]["poster"] = all_infodicts[title_to_poster[title]]["time_and_location"]
    if all_infodicts[i]["type"] == u"Poster":
      if title in title_to_talk:
        all_infodicts[i]["talk"] = all_infodicts[title_to_poster[title]]["time_and_location"]
  return all_infodicts

def verbatim_with_linebreaks(instr):
  output = "\\begin{verbatim}"
  maxlen = len('Out of the Box: Reasoning with Graph Convolution Nets andsomeot')
  numcharprint = 0
  while True:
    if numcharprint + maxlen >= len(instr):
      return output + instr[numcharprint:] + "\\end{verbatim}\n"
    else:
      idx = instr.rfind(' ', numcharprint, numcharprint + maxlen)
      if idx == -1:
        idx = len(instr)
      chunk = instr[numcharprint:idx]
      output += chunk + "\n"
      numcharprint += len(chunk) + 1

def infodict_to_latex(infodict):
  output = verbatim_with_linebreaks(infodict["title"])
  output += infodict["time_and_location"] + "\\\\ \n"
  output += infodict["type"] + " -- " + infodict["session"] + "\\\\ \n"
  if infodict["presenter"]:
    output += infodict["presenter"] + "\\\\ \n"
  if "poster" in infodict.keys():
    output += "Poster " + infodict["poster"] + "\\\\ \n"
  output += ""
  return output

def sort_and_print_infodicts(all_infodicts, print_posters):
  '''
  The talks are not organized by track, I try to fix that.
  '''
  output = ""
  session_to_start = {}
  session_to_end = {}
  session_to_all_event = {}
  for infodict in all_infodicts:
    if infodict["type"] in [u"Oral", u"Spotlight", u"Demonstration"]:
      if infodict["session"] not in session_to_start:
        session_to_start[infodict["session"]] = infodict["time_and_location"]
      session_to_end[infodict["session"]] = infodict["time_and_location"]
      if infodict["session"] not in session_to_all_event:
        session_to_all_event[infodict["session"]] = []
      session_to_all_event[infodict["session"]].append(infodict)
  
  current_day = None
  sessions_already_printed = {}
  sorted_infodicts = []
  for infodict in all_infodicts:
    # if we get to a new day, print the date and time
    if infodict["time_and_location"].find('st ') != -1:
      ordinal = "st "
    elif infodict["time_and_location"].find('rd ') != -1:
      ordinal = "rd "
    elif infodict["time_and_location"].find('th ') != -1:
      ordinal = "th "
    else:
      raise ValueError("could not find ordinal for " + infodict["time_and_location"])
    day = infodict["time_and_location"][0:infodict["time_and_location"].find(ordinal) + 2]
    if current_day != day:
      output += "\\newpage\n"
      output += "\\lhead{\\scriptsize NeurIPS printable schedule " + day + "}\n"
      output += "\\section*{" + day + "}\n"
    current_day = day
    if infodict["type"] in [u"Oral", u"Spotlight", u"Demonstration"]:
      if infodict["session"] not in sessions_already_printed:
        output += "\\section*{" + infodict["session"] + "} \n"
        output += "\\textbf{" + session_to_start[infodict["session"]] + " -- " + session_to_end[infodict["session"]] + "} \n"
        sessions_already_printed[infodict["session"]] = None
        for event in session_to_all_event[infodict["session"]]:
          output += infodict_to_latex(event)
    elif infodict["type"] == u"Poster":
      if print_posters:
        if infodict["session"] not in sessions_already_printed:
          output += "\\section*{" + infodict["session"] + "} \n"
          sessions_already_printed[infodict["session"]] = None
        output += infodict_to_latex(infodict)
    else:
      output += infodict_to_latex(infodict)
  return output

def generate_xetex(all_infodicts, filename, day, print_posters):
  writer = codecs.open(filename, "w", "utf-8")
  #writer = open(filename,"w")
  writer.write("\\documentclass{article}\n")
  writer.write("\\usepackage[a4paper, margin=2cm]{geometry}")
  writer.write("\\usepackage[mathletters]{ucs}\n")
  writer.write("\\usepackage[utf8x]{inputenc}\n")
  writer.write("\\usepackage{color}\n")
  writer.write("\\usepackage{listings}\n")
  writer.write("\\lstset{basicstyle=\\ttfamily, breaklines=true}\n")
  writer.write("\\usepackage{multicol}\n")
  writer.write("\\usepackage{fancyhdr}\n")
  writer.write("\\usepackage{hyperref}\n")
  writer.write("\\usepackage{verbatim}\n\n")
  
  writer.write("\\pagestyle{fancy}\n")
  writer.write("\\fancyhf{}\n")
  writer.write("\\rhead{\\scriptsize By Calvin Seward \\url{github.com/cseward/NeurIPS_PDF}}\n")
  writer.write("\\cfoot{\\scriptsize\\thepage}\n\n")
  
  writer.write("\\begin{document}\n")
  writer.write("\\begin{multicols}{2}\n")
  writer.write("\\scriptsize\n")
  #writer.write("\\twocolumn\n")
  writer.write(sort_and_print_infodicts(all_infodicts, print_posters))
  writer.write("\\end{multicols}{2}\n")
  writer.write("\\end{document}\n")
  
  writer.close()
  
def download_and_save_information():
  for i in range(4):
    all_infodicts = scrape_one_day("https://nips.cc/Conferences/2018/Schedule?day=" + str(i))
    all_infodicts = crosslink_posters_and_talks(all_infodicts)
  
    with open("pickle_files/day_" + str(i) + ".pkl", "wb") as f:
      pickle.dump(all_infodicts, f)

def create_pdfs():
  with open("pickle_files/day_0.pkl", "rb") as f:
    all_infodicts_0 = pickle.load(f)
  generate_xetex(all_infodicts_0, "tex_files/monday_dec_3.tex", "Monday Dec.\ 3th", True)
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/monday_dec_3.tex"])
  subprocess.call(["cp", "tex_files/monday_dec_3.pdf", "."])
  
  with open("pickle_files/day_1.pkl", "rb") as f:
    all_infodicts_1 = pickle.load(f)
  generate_xetex(all_infodicts_1, "tex_files/tuesday_dec_4_with_poster.tex", "Tuesday Dec.\ 4th", True)
  generate_xetex(all_infodicts_1, "tex_files/tuesday_dec_4_no_poster.tex", "Tuesday Dec.\ 4th", False)
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/tuesday_dec_4_with_poster.tex"])
  subprocess.call(["cp", "tex_files/tuesday_dec_4_with_poster.pdf", "."])
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/tuesday_dec_4_no_poster.tex"])
  subprocess.call(["cp", "tex_files/tuesday_dec_4_no_poster.pdf", "."])

  with open("pickle_files/day_2.pkl", "rb") as f:
    all_infodicts_2 = pickle.load(f)
  generate_xetex(all_infodicts_2, "tex_files/wednesday_dec_5_with_poster.tex", "Wednesday Dec.\ 5th", True)
  generate_xetex(all_infodicts_2, "tex_files/wednesday_dec_5_no_poster.tex", "Wednesday Dec.\ 5th", False)
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/wednesday_dec_5_with_poster.tex"])
  subprocess.call(["cp", "tex_files/wednesday_dec_5_with_poster.pdf", "."])
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/wednesday_dec_5_no_poster.tex"])
  subprocess.call(["cp", "tex_files/wednesday_dec_5_no_poster.pdf", "."])

  with open("pickle_files/day_3.pkl", "rb") as f:
    all_infodicts_3 = pickle.load(f)
  generate_xetex(all_infodicts_3, "tex_files/thursday_dec_6_with_poster.tex", "Thursday Dec.\ 6th", True)
  generate_xetex(all_infodicts_3, "tex_files/thursday_dec_6_no_poster.tex", "Thursday Dec.\ 6th", False)
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/thursday_dec_6_with_poster.tex"])
  subprocess.call(["cp", "tex_files/thursday_dec_6_with_poster.pdf", "."])
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/thursday_dec_6_no_poster.tex"])
  subprocess.call(["cp", "tex_files/thursday_dec_6_no_poster.pdf", "."])

  all_infodicts = all_infodicts_0 + all_infodicts_1 + all_infodicts_2 + all_infodicts_3
  
  generate_xetex(all_infodicts, "tex_files/tutorial_and_main_conference_with_poster.tex", "Monday Dec.\ 3th -- Thursday Dec.\ 6th", True)
  generate_xetex(all_infodicts, "tex_files/tutorial_and_main_conference_no_poster.tex", "Monday Dec.\ 3th -- Thursday Dec.\ 6th", False)
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/tutorial_and_main_conference_with_poster.tex"])
  subprocess.call(["cp", "tex_files/tutorial_and_main_conference_with_poster.pdf", "."])
  subprocess.call(["pdflatex", "-output-directory", "tex_files", "tex_files/tutorial_and_main_conference_no_poster.tex"])
  subprocess.call(["cp", "tex_files/tutorial_and_main_conference_no_poster.pdf", "."])


if __name__=="__main__":
  download_and_save_information()
  create_pdfs()