#!/usr/bin/python3

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from zipfile import ZipFile
from datetime import datetime

import os
import shutil
import sys
import uuid
import zipfile
import logging
import traceback
import getpass
import paramiko

import time


class VUPSpider:
    firstReport = True
    zip_obj = None
    driver = None
    params = None
    logger = None

    def __init__(self, driver, params):
        if params.password == '{prompt}':
            params.password = getpass.getpass(
                prompt='Enter your password: ')
        if params.upload_password == '{prompt}':
            params.upload_password = getpass.getpass(
                prompt='Enter your upload_password: ')
        elif params.upload_password == '{password}':
            params.upload_password = params.password

        self.driver = driver
        self.params = params
        self.logger = logging.getLogger()
        logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s')
        self.logger.setLevel(params.log_level)

    def wait_for_element(self, query, wait=None, clickable=False, multi=False):
        if not wait:
            wait = params.wait_secs
        driver.implicitly_wait(params.wait_secs)
        if clickable:
            return WebDriverWait(self.driver, wait).until(
                EC.element_to_be_clickable((By.XPATH, query)))
        if multi:
            return WebDriverWait(self.driver, wait).until(
                EC.visibility_of_all_elements_located((By.XPATH, query)))
        return WebDriverWait(self.driver, wait).until(
            EC.visibility_of_element_located((By.XPATH, query)))

    def click_element(self, query, wait=None):
        if not wait:
            wait = params.wait_secs
        # There is a race with the popup window here, just try multiple times
        while True:
            elem = self.wait_for_element(query, clickable=True)
            try:
                elem.click()
                break
            except:
                self.logger.warning(
                    f'Unable to click {query}, trying again...')
                time.sleep(1)

        return elem

    def scroll_left_element(self, query, wait=None):
        if not wait:
            wait = params.wait_secs
        # There is a race with the popup window here, just try multiple times
        while True:
            elem = self.wait_for_element(query)
            try:
                driver.execute_script(
                    'arguments[0].scrollLeft+=1000000; setTimeout(function(){ arguments[0].scrollLeft-=1; },  999);', elem)
                time.sleep(1)
                break
            except:
                self.logger.warning(
                    f'Unable to scroll {query}, trying again...')
                time.sleep(1)

        return elem

    def get_last_downloaded_csv(self):
        home = os.path.expanduser('~')
        path = os.path.join(home, "Downloads")
        files = os.listdir(path)
        csvs = [os.path.join(path, f)
                for f in files if f.lower().endswith('.csv')]
        if len(csvs) == 0:
            return None
        time_sorted_csvs = sorted(csvs, key=os.path.getmtime)
        csv = time_sorted_csvs[-1]
        return csv

    def login(self):
        username_input = '//input[@id="j_username"]'
        password_input = '//input[@id="passwordInput"]'

        driver = self.driver
        driver.get(params.projects_url)
        elem = self.wait_for_element(username_input)
        elem.clear()
        elem.send_keys(self.params.username)
        elem.send_keys(Keys.RETURN)

        elem = self.wait_for_element(password_input)
        elem.clear()
        elem.send_keys(self.params.password)
        elem.send_keys(Keys.RETURN)

    def wait_for_home_page(self, wait=None):
        home_element = '//span[starts-with(text(), "R/0")][1]'

        if not wait:
            wait = params.wait_secs*2
        self.wait_for_element(home_element, wait=wait)

    def init_home_page(self):
        fpo_ready_button = '//div[@class="highcharts-container"][1]'
        fpo_ready_alt = '//span[text()="FPO overzicht"]'
        fpo_ready = '//span[@title="FPO"]'

        # Need to click here a few times for the FPO top button to show up...
        self.click_element(fpo_ready_button)
        while True:
            try:
                self.wait_for_element(fpo_ready, wait=1, clickable=True)
                break
            except:
                self.click_element(fpo_ready_alt)  # just to change focus
                self.click_element(fpo_ready_button)

    def refresh_home_page(self):
        self.driver.refresh()
        self.wait_for_home_page()
        self.init_home_page()

    def get_projects(self):
        project_cell = '//span[starts-with(text(), "R/0")][1]/ancestor::div[contains(@class, "tableDivTable")][1]//div[@data-tablecol="{column}"]//span'
        project_id_cell = project_cell.format(column='0')
        project_desc_cell = project_cell.format(column='1')

        while True:
            project_ids = self.wait_for_element(project_id_cell, multi=True)
            project_descs = self.wait_for_element(
                project_desc_cell, multi=True)

            project_ids = [e.text for e in project_ids if len(e.text) > 0]
            project_descs = [e.text for e in project_descs if len(e.text) > 0]
            if len(project_ids) > 0 and len(project_ids) == len(project_descs):
                self.logger.info("Found projects:")
                for id, desc in zip(project_ids, project_descs):
                    print(f" - {id}: {desc}")
                break
            else:
                self.logger.warning("No projects found, trying again...")
                time.sleep(1)

        return project_ids, project_descs

    def select_project(self, id):
        search_input = '//input[starts-with(@placeholder, "Knip en plak project nummer")]'
        search_button = '//div[text()="Zoek op project:"]/ancestor::button[1]'
        reset_button = '//div[text()="Reset project:"]/ancestor::button[1]'

        self.logger.info(f'Selecting project {id}...')
        elem = self.wait_for_element(search_input)
        elem.clear()
        elem.send_keys(id)
        self.click_element(search_button)
        self.wait_for_element(reset_button, clickable=True)

    def export_report(self):
        more_button = '//span[@title="More Actions"]'
        export_button = '//li[@title="Export"]'
        scope_select = '//div[text()="Point of view"]/ancestor::div[1]'
        delimiter_select = '//div[text()="Comma ,"]/ancestor::div[1]'
        delimiter_opts = [',', ';', '\t', ' ', '.', ':', '-']
        export_ok_button = '//bdi[text()="OK"]/ancestor::button[1]'

        self.click_element(more_button)
        self.click_element(export_button)

        last_csv = self.get_last_downloaded_csv()

        self.wait_for_element(scope_select).send_keys(Keys.ARROW_DOWN)
        if params.csv_delimiter not in delimiter_opts:
            self.logger.warning(
                f'Invalid csv delimiter \'{params.csv_delimiter}\', defaulting to \',\'')
            params.csv_delimiter = ','
        delimiter_index = delimiter_opts.index(params.csv_delimiter)
        e = self.wait_for_element(delimiter_select)
        for i in range(delimiter_index):
            e.send_keys(Keys.ARROW_DOWN)

        self.wait_for_element(export_ok_button).send_keys(Keys.SPACE)

        csv = None
        while True:
            time.sleep(1)
            csv = self.get_last_downloaded_csv()
            if csv != last_csv:
                break

        return csv

    def save_report(self, csv, report_file, project_id, project_desc):
        if self.firstReport:
            if params.storage_dir_cleanup and os.path.exists(params.storage_dir):
                shutil.rmtree(params.storage_dir)
            if not os.path.exists(params.storage_dir):
                os.makedirs(params.storage_dir)
            if params.report_zip_file:
                zip_filebase = params.report_zip_file.format(
                    username=params.username,
                    date=datetime.now().isoformat().replace(':', '-'),
                    date_min=datetime.now().isoformat(timespec='minutes').replace(':', '-'),
                    date_sec=datetime.now().isoformat(timespec='seconds').replace(':', '-'),
                    date_ms=datetime.now().isoformat(timespec='milliseconds').replace(':', '-'),
                    uuid=uuid.uuid4()
                )
                zip_file = os.path.join(params.storage_dir, zip_filebase)
                self.zip_obj = ZipFile(zip_file, 'a',
                                       compression=zipfile.ZIP_DEFLATED)
            self.firstReport = False

        filebase = report_file.format(
            ProjectId=project_id.replace('/', ''),
            ProjectDescription=project_desc
        )
        file = os.path.join(params.storage_dir, filebase)
        shutil.move(csv, file)

        if self.zip_obj:
            self.zip_obj.write(file, arcname=filebase)

        self.logger.info(f'Saved {file}')

        return

    def download_report(self, project_id, project_desc, report_name, report_file,
                        tab_button, table_leftmost_cell, table_rightmost_cell, scrollable):
        if not report_file:
            self.logger.info(
                f'Skipping report for {project_id} ({report_name})...')
            return
        self.click_element(tab_button)
        self.wait_for_element(table_leftmost_cell, clickable=True)
        self.scroll_left_element(scrollable)
        self.click_element(table_rightmost_cell)

        csv = self.export_report()
        self.save_report(csv, report_file, project_id, project_desc)

    def upload(self, local_file):
        logger = logging.getLogger('paramiko')
        logger.setLevel(params.log_level)

        # Open hostkey file
        hostkey_file = None
        hostkey = None
        hostname = params.upload_hostname
        try:
            hostkey_file = os.path.expanduser(
                os.path.join('~', '.ssh', 'known_hosts'))
            if not os.path.isfile(hostkey_file):
                hostkey_file = os.path.expanduser(
                    os.path.join('~', 'ssh', 'known_hosts'))
            host_keys = paramiko.util.load_host_keys(hostkey_file)
        except IOError:
            logger.error('Unable to open host keys file')
            sys.exit(1)
        logger.info('Using host key file %s' % hostkey_file)

        # Locate hostkey for hostname
        if hostname not in host_keys:
            logger.error('Host name not in host keys file, ssh manually first')
            sys.exit(1)
        hostkeytype = host_keys[hostname].keys()[0]
        hostkey = host_keys[hostname][hostkeytype]
        logger.info('Using host key of type %s' % hostkeytype)

        # Connect to hostname and upload file
        try:
            t = paramiko.Transport((hostname, params.upload_ssh_port))
            t.connect(hostkey, params.upload_username,
                      params.upload_password)
            sftp = paramiko.SFTPClient.from_transport(t)
            basefile = os.path.basename(local_file)
            remote_file = params.upload_hostdir + '/' + basefile
            logger.info('Uploading localhost:{local} -> {h}:{remote}'.format(
                local=local_file, h=hostname, remote=remote_file))
            sftp.put(local_file, remote_file)
            t.close()
        except Exception as e:
            logger.error('Caught exception: %s: %s' % (e.__class__, e))
            traceback.print_exc()
            try:
                t.close()
            except:
                pass
            sys.exit(1)

    def finalize(self):
        if self.zip_obj:
            self.zip_obj.close()
            self.logger.info(f'Saved {self.zip_obj.filename}')

        if params.upload_hostname:
            self.upload(self.zip_obj.filename)

    def download_expenses_overview(self, project_id, project_desc):
        tab_button = '//span[@title="Boekingsregels"]'
        table_leftmost_cell = '//span[starts-with(text(),"WBS-element")]'
        table_rightmost_cell = '//span[starts-with(text(),"Gealloceerde FTE")]'
        scrollable = '//span[starts-with(text(),"Gealloceerde FTE")]/ancestor::div[starts-with(@id, "__container")][1]'

        self.download_report(project_id, project_desc, 'expenses', params.expenses_file,
                             tab_button, table_leftmost_cell, table_rightmost_cell, scrollable)

    def download_personnel_overview(self, project_id, project_desc):
        tab_button = '//span[@title="Personeel"]'
        table_leftmost_cell = '//span[starts-with(text(),"WBS-element")]'
        table_rightmost_cell = '//span[starts-with(text(),"Nog te besteden")]'
        scrollable = '//div[starts-with(@class,"scrollbarContainer horizontal")][1]'

        self.download_report(project_id, project_desc, 'personnel', params.personnel_file,
                             tab_button, table_leftmost_cell, table_rightmost_cell, scrollable)

    def download_project_overview(self, project_id, project_desc):
        tab_button = '//div[text()="FPO gegevens"]/ancestor::button[1]'
        table_leftmost_cell = '//span[starts-with(text(),"Contractbedrag")]'
        table_rightmost_cell = '//span[starts-with(text(),"Delta Contract Begroting")]'
        scrollable = '//div[starts-with(@class,"scrollbarContainer horizontal")][1]'

        self.download_report(project_id, project_desc, 'project', params.project_file,
                             tab_button, table_leftmost_cell, table_rightmost_cell, scrollable)

    def download_per_project_overviews(self, project_ids, project_descs):
        time_start = time.perf_counter()
        first = True
        for id, desc in zip(project_ids, project_descs):
            if first:
                first = False
            else:
                self.refresh_home_page()

            self.select_project(id)
            self.download_project_overview(id, desc)
            if params.force_per_project_reports:
                self.download_personnel_overview(id, desc)
                self.download_expenses_overview(id, desc)
            time_taken = time.perf_counter() - time_start
            self.logger.info(f'Took {time_taken} seconds')
            time_start = time.perf_counter()

    def run(self):
        # Login and load home page
        time_begin = time.perf_counter()
        self.login()
        self.wait_for_home_page(wait=90)
        (project_ids, project_descs) = self.get_projects()
        self.init_home_page()

        # Download global reports
        if not params.force_per_project_reports:
            self.download_personnel_overview("All", "All")
            self.download_expenses_overview("All", "All")
            self.refresh_home_page()

        # Download per-project reports
        if params.project_file or params.force_per_project_reports:
            self.download_per_project_overviews(project_ids, project_descs)

        # Finalize and upload as needed
        self.finalize()
        time_taken = time.perf_counter() - time_begin
        self.logger.info(f'Overall run took {time_taken} seconds')


#
# main()
#
try:
    import params
except ImportError:
    print("Please create params.py based on params_default.py first.")
    sys.exit(1)

driver = webdriver.Chrome()
driver.maximize_window()

spider = VUPSpider(driver, params)
spider.run()
driver.close()
