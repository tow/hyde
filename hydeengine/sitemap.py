from django.conf import settings
from file_system import Folder
import os
import operator 
from datetime import datetime
from datetime import date

def make_url(root, child):
    return root.rstrip("/") + "/" + child.lstrip("/")

class SitemapNode(object):
    def __init__(self, parent, folder, name=None):
        super(SitemapNode, self).__init__()
        self.folder = folder
        self.parent = parent
        self.pages = []
        self.children = []
        self.listing_page = None
        if not name:
            self.name = folder.name
        else:
            self.name = name
        
    def __repr__(self):
        return self.folder.path
        
    @property
    def ancestors(self):
        node = self
        ancestors = []
        while not node.isroot:
            ancestors.append(node)
            node = node.parent
        ancestors.append(node)
        ancestors.reverse()
        return ancestors
        
    @property
    def depth(self):
        node = self
        depth = 0
        while node.parent:
            node = node.parent
            depth = depth + 1
        return depth
        
    @property
    def module(self):
        module = self
        while(module.parent and module.parent.parent):
            module = module.parent
        return module

    def get_node_for(self, file_system_entity):
        if file_system_entity.path == self.folder.path:
            return self
        current = self    
        if not current.isroot:
            current = self.parent
            return current.get_node_for(file_system_entity)
        for node in current.walk():
            if node.folder.path == file_system_entity.path:
                return node
        return None
   
    def get_parent_of(self, file_system_entity):
        return self.get_node_for(file_system_entity.parent)
    
    @property
    def has_listing(self):
        return not self.listing_page is None
    
    @property
    def listing_url(self):
        return self.listing_page.url
    
    @property
    def full_url(self):
        if settings.GENERATE_ABSOLUTE_FS_URLS:
            return self.url        
        else:
            return make_url(settings.SITE_WWW_URL, self.url)
            
    @property
    def url(self):
        if settings.GENERATE_ABSOLUTE_FS_URLS:
            return self.folder.get_mirror_folder(
                        settings.CONTENT_DIR, settings.DEPLOY_DIR,
                        ignore_root=True).path
        else:
            site_root = ""
            if hasattr(settings, "SITE_ROOT"):
                site_root = settings.SITE_ROOT.rstrip("/")
                
            url = site_root + "/" + self.folder.get_fragment(
                                    settings.CONTENT_DIR
                                    ).lstrip(os.sep)
            return url.rstrip("/")
    
    @property
    def isroot(self):
        return self.parent is None
        
    @property 
    def isleaf(self):
        return not self.children
        
    @property
    def siblings(self):
        if self.isroot: 
            return None
        siblings = []
        siblings = self.parent.children[:]
        siblings.remove(self)
        return siblings
        
    @property
    def next_siblings(self):
        if not self.parent: 
            return None
        siblings = self.parent.children
        index = siblings.index(self)
        return siblings[index+1:]
        
    @property
    def next_sibling(self):
        sibs = self.next_siblings
        if sibs:
            return sibs[0]
        return None
        
    @property
    def prev_siblings(self):
        if not self.parent: 
            return None
        siblings = self.parent.children
        index = siblings.index(self)
        return siblings[:index]

    @property
    def prev_sibling(self):
        sibs = self.prev_siblings
        if sibs:
            return sibs[0]
        return None
    
    def append_child(self, folder):
        node = SitemapNode(self, folder)
        self.children.append(node)
        return node
        
    def add_page(self, page):
        previous = None
        if len(self.pages):
            previous = self.pages[len(self.pages) - 1]
            if previous and not previous.display_in_list:
                previous = previous.previous
        page.previous = previous
        self.pages.append(page)
        page.node = self
        page.module = self.module
        if not hasattr(page, "exclude"):
            page.exclude = False
        if not hasattr(page, "created") or not page.created:
            page.created = datetime.strptime(
                            "2000-01-01", 
                            "%Y-%m-%d")			
        if not hasattr(page, "updated") or not page.updated:
            page.updated = page.created

        #if the created or updated is a date, we should convert to a
        if (hasattr(page, "created") and type(getattr(page, "created")) == date):
            page.created = datetime(page.created.year, page.created.month, page.created.day)
        if (hasattr(page, "updated") and type(getattr(page, "updated")) == date):
            page.updated = datetime(page.updated.year, page.updated.month, page.updated.day)
            
        if page.name_without_extension.lower() == self.name.lower() or \
           page.name_without_extension.lower() in settings.LISTING_PAGE_NAMES:
            self.listing_page = page
            page.listing = True
        elif (hasattr(page, "listing") and page.listing 
            and not self.listing_page):
            self.listing_page = page
        else:
            page.listing = False
            
        page.display_in_list = (not page.listing and 
                                not page.exclude and 
                                page.kind == "html")
        if previous and page.display_in_list:
            previous.next = page

        # clean url generation requires knowing whether or not a page is a
        # listing page prior to generating its url
        if settings.GENERATE_CLEAN_URLS:
            if page.listing:
                url = str(Folder(self.url))
            else:
                url = str(Folder(self.url).child(page.name_without_extension))
            if settings.APPEND_SLASH or not url:
                url += "/"
        elif settings.GENERATE_ABSOLUTE_FS_URLS:
            url = Folder(self.url).child(page.name)
        else:
            url = make_url(self.url, page.name)
        page.url = url
        page.full_url = make_url(settings.SITE_WWW_URL, page.url)
        #import sys
        #sys.stderr.write("Full url: %s     Url: %s \n" % (page.full_url, page.url))
   
    def sort_and_link_pages(self):
        self.pages.sort(key=operator.attrgetter("created"), reverse=True)
        prev = None
        for page in self.pages:
         if page.display_in_list:
             if prev:
                 prev.next = page
                 page.prev = prev
             page.next = None
             prev = page
        for node in self.children:
            node.sort_and_link_pages()
            
    def walk(self):
        yield self
        for child in self.children:
            for node in child.walk():
                yield node

    def walk_pages(self):            
        for node in self.walk():
            for page in node.pages:
                yield page
        