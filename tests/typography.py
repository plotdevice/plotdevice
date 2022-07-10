# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class TypographyTests(PlotDeviceTestCase):
    @reference('typography/typography-basics.png')
    def test_typography_basics(self):
        # tut/Typography (1)
        size(200, 90)
        x, y = 24, 56
        arc(x,y, 6, fill='red') # the baseline ‘origin’ pt
        
        font('Avenir', 'black', 32)
        text('München', x, y)

    @reference('typography/typography-basic-lines.png')
    def test_typography_basic_lines(self):
        # tut/Typography (2)
        size(200, 90)
        x, y = 24, 24
        font('Baskerville', 24, italic=True)
        text('One.\nTwo.\nThree.', x, y)

    @reference('typography/typography-basic-block.png')
    def test_typography_basic_block(self):
        # tut/Typography (3)
        size(300, 220)
        lorem = "Early in the bright sun-yellowed morning, Stuart McConchie swept the sidewalk before Modem TV Sales & Service, hearing the cars along Shattuck Avenue and the secretaries hurrying on high heels to their offices, all the stirrings and fine smells of a new week, a new time in which a good salesman could accomplish things."
        x, y = 12, 24
        
        font("american typewriter", 16)
        layout(leading=1.3)
        text(lorem, x, y, 270)

    @reference('typography/typography-basic-block-height.png')
    def test_typography_basic_block_height(self):
        # tut/Typography (4)
        size(280, 180)
        lorem = "It was about eleven o'clock in the morning, mid October, with the sun not shining and a look of hard wet rain in the clearness of the foothills."
        font('baskerville', 16)
        
        # left: fixed width, unlimited height
        text(lorem, 10,20, 120)
        
        # right: clip to fixed width and height
        text(lorem, 150,20, 120,60)

    @reference('typography/typography-basic-overrides.png')
    def test_typography_basic_overrides(self):
        # tut/Typography (5)
        size(200, 172)
        fill(0.3)
        font('avenir next', 'medium', 32)
        
        text('Good', 100,40)
        text('big', 10,120, weight='bold', size=120, sc=True)
        text('or Red', 16,155, fill='red')

    @reference('typography/typography-align-point.png')
    def test_typography_align_point(self):
        # tut/Typography (6)
        size(200, 180)
        x = WIDTH/2
        
        text("left",   x, 50)
        text("center", x, 100, align=CENTER)
        text("right",  x, 150, align=RIGHT)
        
        with stroke(.7), pen(dash=3):
          line(x,0, x,HEIGHT)

    @reference('typography/typography-align-block.png')
    def test_typography_align_block(self):
        # tut/Typography (7)
        size(200, 180)
        x, w = 30, 140
        
        text("left",   x,50,  w)
        text("center", x,100, w, align=CENTER)
        text("right",  x,150, w, align=RIGHT)
        
        with stroke(.7), pen(dash=3):
            line(x,0, dy=HEIGHT)
            line(x+w,0, dy=HEIGHT)

    @reference('typography/typography-styles-font.png')
    def test_typography_styles_font(self):
        # tut/Typography (8)
        size(200, 220)
        font('jenson', 'medium', 22)
        text("September 1972", 20,40)
        
        font(osf=True) # old-style figures
        text("September 1972", 20,90)
        
        font(sc=True) # small-caps
        text("September 1972", 20,140)
        
        font(sc=all, tracking=50) # letter-spacing
        text("September 1972", 20,190)

    @reference('typography/typography-styles-layout.png')
    def test_typography_styles_layout(self):
        # tut/Typography (9)
        size(200, 210)
        lorem = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        
        font('Georgia', 14)
        text(lorem, 10,20, 80)
        
        layout(align=RIGHT, leading=1.6)
        text(lorem, 110,20, 80)

    @reference('typography/typography-styles-named.png')
    def test_typography_styles_named(self):
        # tut/Typography (10)
        size(200, 240)
        stylesheet('emph', italic=True)
        stylesheet('bright', weight='heavy', fill='red')
        
        font('Avenir Next', 20)
        text('handgloves', 10,40)
        text('handgloves', 10,70, style='emph')
        text('handgloves', 10,100, style='bright')
        
        font('Joanna MT', 28)
        text('handgloves', 10,150)
        text('handgloves', 10,180, style='emph')
        text('handgloves', 10,210, style='bright')

    @reference('typography/typography-basic-append.png')
    def test_typography_basic_append(self):
        # tut/Typography (11)
        size(300, 182)
        names = ['red', 'tan', 'aqua', 'blue', 'cyan', 'gold', 'gray', 'lime', 'peru', 'pink', 'plum', 'snow', 'teal', 'azure', 'beige', 'brown', 'coral', 'green', 'ivory', 'khaki', 'linen', 'olive', 'deepskyblue', ]
        background(.15)
        font('gill sans')
        
        t = text(10,26, 280, fill=.5)
        for name in names:
            t.append(name, fill=name)
            t.append(' / ', weight='light')

    @reference('typography/typography-styles-inline.png')
    def test_typography_styles_inline(self):
        # tut/Typography (12)
        size(300, 72)
        stylesheet('caps', sc=True, tracking=40)
        stylesheet('bold', weight='bold')
        
        font('avenir next', 19)
        text(12,42, xml='correct <caps>horse <bold>battery</bold> staple</caps>')

    @reference('typography/typography-layout-bounds.png')
    def test_typography_layout_bounds(self):
        # tut/Typography (13)
        size(300, 210)
        karlton = "There are only two hard things in Computer Science: cache invalidation and naming things."
        
        font('american typewriter', 20)
        t = text(20, 40, 200, 150, str=karlton)
        
        nofill()
        rect(t.frame, stroke=.6)
        rect(t.bounds, stroke='red', dash=4)

    @reference('typography/typography-layout-lines.png')
    def test_typography_layout_lines(self):
        # tut/Typography (14)
        size(300, 210)
        jabber = "Twas brillig, and the slithy toves did gyre and gimble in the wabe: all mimsy were the borogoves, and the mome raths outgrabe."
        
        font('american typewriter', 20)
        t = text(20,40, 250,160, str=jabber)
        self.assertAlmostEqual(len(t.lines), 6)
        
        nofill()
        slug = t.lines[2] # metrics of line 3
        rect(slug.frame, stroke=0.7)
        rect(slug.bounds, stroke='red', dash=4)

    @reference('typography/typography-layout-fragments.png')
    def test_typography_layout_fragments(self):
        # tut/Typography (15)
        size(300, 210)
        font('Joanna MT', 80, italic=True)
        t = text(20,120, str='Axiomatic')
        
        first = t[0]
        middle = t[3:6]
        last = t[-1]
        
        nofill()
        rect(first.bounds, stroke='red')
        rect(middle.bounds, stroke='orange')
        rect(last.bounds, stroke='green')

    @reference('typography/typography-layout-glyphs.png')
    def test_typography_layout_glyphs(self):
        # tut/Typography (16)
        size(300, 110)
        font('Helvetica Neue', 64)
        t = text(20, 72, str="Spokane")
        
        nofill()
        for glyph in t:
            rect(glyph.bounds, stroke=.9)
        
        for glyph in t:
            rect(glyph.path.bounds, stroke='red')

    @reference('typography/typography-layout-words.png')
    def test_typography_layout_words(self):
        # tut/Typography (17)
        size(300, 140)
        rhyme = "Tinker, tailor, soldier, sailor, rich man, poor man, begger man, thief"
        
        font('Joanna MT', 32, italic=True)
        t = text(20,40, 270,160, str=rhyme)
        
        nofill()
        for word in t.words:
            rect(word.bounds, stroke=.4, dash=2)

    @reference('typography/typography-layout-find.png')
    def test_typography_layout_find(self):
        # tut/Typography (18)
        size(300, 100)
        font('Palatino', 23)
        t = text(20, 40, 250, str="The frog in the fog bares its fangs in good humor")
        
        for match in t.find('good'): # simple
            rect(match.bounds, stroke='steelblue', fill=None)
        
        for match in t.find(r'f\w+'): # regex
            rect(match.bounds, stroke='firebrick', fill=None)

    @reference('typography/typography-layout-select.png')
    def test_typography_layout_select(self):
        # tut/Typography (19)
        size(300, 140)
        haystack = "...................\n.........<needle>.</needle>.........\n..................."
        
        font('Helvetica Neue', 32)
        t = text(60,32, xml=haystack)
        for match in t.select('needle'):
            rect(match.bounds, stroke='red', fill=None)

    @reference('typography/typography-layout-select2.png')
    def test_typography_layout_select2(self):
        # tut/Typography (20)
        size(300, 240)
        flaubert = "“Five hundred lines for all the class!” shouted in a furious voice stopped, like the Quos ego<fn note=\"A quotation from the Aeneid signifying a threat.\">1</fn>, a fresh outburst. “Silence!” continued the master indignantly, wiping his brow with his handkerchief, which he had just taken from his cap. “As to you, ‘new boy,’ you will conjugate ‘ridiculus sum’<fn note=\"I am ridiculous.\">2</fn> twenty times.”\nThen, in a gentler tone, “Come, you’ll find your cap again; it hasn’t been stolen.”"
        
        font('Adobe Jenson', 14)
        layout(hyphenate=True, indent=True)
        stylesheet('fn', vpos=1, fill='red')
        
        body = text(10,20, 170, xml=flaubert)
        for fn in body.select('fn'):
            note = text('', 190, fn.baseline.y, width=100, italic=True)
            note.append(fn.text, vpos=1)
            note.append(' '+fn.attrs['note'])

    @reference('typography/typography-advanced-margin.png')
    def test_typography_advanced_margin(self):
        # tut/Typography (21)
        size(300, 300)
        dickens = "London. Michaelmas term lately over, and the Lord Chancellor sitting in Lincoln's Inn Hall. Implacable November weather. As much mud in the streets as if the waters had but newly retired from the face of the earth, and it would not be wonderful to meet a Megalosaurus, forty feet long or so, waddling like an elephantine lizard up Holborn Hill. Smoke lowering down from chimney-pots, making a soft black drizzle, with flakes of soot in it as big as full-grown snowflakes—gone into mourning, one might imagine, for the death of the sun. Dogs, undistinguishable in mire. Horses, scarcely better; splashed to their very blinkers. Foot passengers, jostling one another's umbrellas in a general infection of ill temper, and losing their foot-hold at street-corners, where tens of thousands of other foot passengers have been slipping and sliding since the day broke (if this day ever broke), adding new deposits to the crust upon crust of mud, sticking at those points tenaciously to the pavement, and accumulating at compound interest."
        
        font('Baskerville', 13)
        x, y = 0, 20
        w, h = 300, 90
        
        layout(margin=0) # the default
        text(x,y, w,h, str=dickens)
        y += 100
        
        layout(margin=40) # left-side margin
        text(x,y, w,h, str=dickens)
        y+=100
        
        layout(margin=(80,40)) # both-sides margin
        text(x,y, w,h, str=dickens)

    @reference('typography/typography-advanced-spacing.png')
    def test_typography_advanced_spacing(self):
        # tut/Typography (22)
        size(300, 200)
        txt = "Paragraph one has five words.\nParagraph two is shorter.\nParagraph three is followed by a snowman.\n☃ "
        font(13)
        
        layout(spacing=0) # the default
        text(20,30, 100, str=txt)
        
        layout(spacing=1) # add 1 lineheight of extra space
        text(150,30, 120, str=txt)

    @reference('typography/typography-advanced-indent.png')
    def test_typography_advanced_indent(self):
        # tut/Typography (23)
        size(300, 320)
        txt="The first paragraph extends to the first carriage return character and will never be indented by default.\nThe second paragraph follows the first and will be indented according to the current layout settings.\nThe third paragraph is just like the second. It is also indented.\n\nA final paragraph, preceded by a blank line, represents the beginning of a new ‘section’ and suppresses any indentation.\n"
        
        layout(indent=1.4)
        font('Georgia', 16)
        text(30,40, width=250, str=txt)

    @reference('typography/typography-advanced-outdent.png')
    def test_typography_advanced_outdent(self):
        # tut/Typography (24)
        size(300, 300)
        txt="The first paragraph extends to the first carriage return character and will be outdented by the negative indentation value.\nThe second paragraph follows the first and will be outdented too.\nThe third paragraph is outdented just like the prior two.\n\nA final paragraph, preceded by a blank line, represents the beginning of a new ‘section’ but is outdented all the same.\n"
        
        layout(indent=-1.4)
        font('Georgia', 16)
        text(30,40, width=250, str=txt)

    @reference('typography/typography-advanced-flow.png')
    def test_typography_advanced_flow(self):
        # tut/Typography (25)
        size(300, 150)
        kafka = 'Someone must have been telling lies about Josef K., he knew he had done nothing wrong but, one morning, he was arrested. Every day at eight in the morning he was brought his breakfast by Mrs. Grubach’s cook. Mrs. Gru-bach was his landlady but today she didn’t come. That had never happened before. K. waited a little while, looked from his pillow at the old woman who lived opposite and who was watching him with an inquisitiveness quite unusual for her, and finally, both hungry and disconcerted, rang the bell. There was immediately a knock at the door and a man entered.'
        
        font('Adobe Garamond', size=10)
        layout(align=JUSTIFY, hyphenate=True)
        t = text(20,20, 120,120, str=kafka)
        for block in t.flow(2):
            block.x += block.width + 20

    @reference('typography/typography-advanced-flow2.png')
    def test_typography_advanced_flow2(self):
        # tut/Typography (26)
        size(300, 330)
        kafka = 'and a man entered. He had never seen the man in this house before. He was slim but firmly built, his clothes were black and close-fitting, with many folds and pockets, buckles and buttons and a belt, all of which gave the impression of being very practical but without making it very clear what they were actually for. “Who are you?” asked K., sitting half upright in his bed. The man, however, ignored the question as if his arrival simply had to be accepted, and merely replied, “You rang?” “Anna should have brought me my breakfast,” said K. He tried to work out who the man actually was, first in silence, just through observation and by thinking about it, but the man didn’t stay still to be looked at for very long. Instead he went over to the door, opened it slightly, and said to someone who was clearly standing immediately behind it, “He wants Anna to bring him his breakfast.” There was a little laughter in the neighbouring room, it was not clear from the sound of it whether there were several people laughing. The strange man could not have learned anything from it that he hadn’t known already, but now he said to K., as if making his report “It is not possible.” “It would be the first time that’s happened,” said K., as he jumped out of bed and quickly pulled on his trousers. “I want to see who that is in the next room, and why it is that Mrs. Grubach has let me be disturbed in this way.” It immediately occurred to him that he needn’t have said this out loud, and that he must to some extent have acknowledged their authority by doing so, but that ...'
        
        font('Adobe Garamond', size=10)
        layout(align=JUSTIFY, hyphenate=True)
        
        def leftright(block):
            if block.idx % 2:
                block.x += block.width + 20
            else:
                block.x = 0
                block.y += block.height + 20
        
        t = text(20,24, 120,120, str=kafka)
        t.flow(all, leftright)

    @reference('typography/typography-advanced-flow3.png')
    def test_typography_advanced_flow3(self):
        # tut/Typography (27)
        size(300, 240)
        welles = 'Before the law, there stands a guard. A man comes from the country, begging admittance to the law. But the guard cannot admit him. May he hope to enter at a later time? That is possible, said the guard. The man tries to peer through the entrance. He’d been taught that the law was to be accessible to every man. “Do not attempt to enter without my permission”, says the guard. I am very powerful. Yet I am the least of all the guards. From hall to hall, door after door, each guard is more powerful than the last. By the guard’s permission, the man sits by the side of the door, and there he waits. For years, he waits. Everything he has, he gives away in the hope of bribing the guard, who never fails to say to him “I take what you give me only so that you will not feel that you left something undone.” Keeping his watch during the long years, the man has come to know even the fleas on the guard’s fur collar. Growing childish in old age, he begs the fleas to persuade the guard to change his mind and allow him to enter. His sight has dimmed, but in the darkness he perceives a radiance streaming immortally from the door of the law. And now, before he dies, all he’s experienced condenses into one question, a question he’s never asked. He beckons the guard. Says the guard, “You are insatiable! What is it now?” Says the man, “Every man strives to attain the law. How is it then that in all these years, no one else has ever come here, seeking admittance?” His hearing has failed, so the guard yells into his ear. “Nobody else but you could ever have obtained admittance. No one else could enter this door! This door was intended only for you! And now, I’m going to close it.” This tale is told during the story called “The Trial”. It’s been said that the logic of this story is the logic of a dream... a nightmare.'
        
        font('Adobe Garamond', size=10)
        t = text(20,26, 80,120, str=welles)
        for block in t.flow(3):
            block.x += block.width + 10
            block.y += 40
        
        nofill()
        rect(t.bounds, stroke=.6)
        for block in t.blocks:
            rect(block.bounds, stroke='red', dash=4)

    @reference('typography/typography-advanced-flow4.png')
    def test_typography_advanced_flow4(self):
        # tut/Typography (28)
        size(300, 180)
        fake_id = "NAME\fJean d’Eau\fEYES\fViolet\fHEIGHT\f3'5\"\fAGE\f137\fADDRESS\f123 Fake St.\nSpringfield, IL 62705"
        
        font('Avenir', size=14)
        t = text(20,26, str=fake_id)
        for block in t.flow():
            if block.idx % 2:
                block.x += 100
            else:
                block.x = 0
                block.y += 30

    @reference('typography/font.png')
    def test_font(self):
        # ref/Typography/commands/font()
        size(125, 125)
        fill(0.2)
        font("Helvetica", 35)
        text("hello", 10, 50)
        with font("bold", 16, italic=True):
            text("cruel", 10, 69)
        text("world", 10, 95)

    @reference('typography/layout.png')
    def test_layout(self):
        # ref/Typography/commands/layout()
        size(125, 125)
        layout(align=RIGHT, leading=2)
        text(10,22, 100, str="Hide and/or Seek")

    @reference('typography/stylesheet-cascade.png')
    def test_stylesheet_cascade(self):
        # ref/Typography/commands/stylesheet()
        size(125, 125)
        markup = "<it>Bip <bf>Blip</bf></it>"
        stylesheet("it", italic=True)
        stylesheet("bf", weight='black')
        with font("Baskerville", 22):
            text(20,40, xml=markup)
        with font("Avenir", 18), fill('red'):
            text(20,80, xml=markup)

    @reference('typography/textpath.png')
    def test_textpath(self):
        # ref/Typography/commands/textpath()
        size(125, 125)
        font("Helvetica", 65)
        path = textpath("clip", 10, 70)
        with clip(path):
            image("tests/_in/header.jpg", -300, -150)

    @reference('typography/align.png')
    def test_align(self):
        # ref/Typography/compat/align()
        size(125, 125)
        x = 62
        line(x,10, x,115, dash=3, stroke=.7)
        font(12)
        align(RIGHT)
        text("Conapt", x,25)
        align(LEFT)
        text("Kipple", x,65)
        align(CENTER)
        text("Homeopape", x,105)

    @reference('typography/align-block.png')
    def test_align_block(self):
        # ref/Typography/compat/align()
        size(125, 125)
        quip = "Twas brillig and the slithy toves"
        x,y = 10,55
        font(16)
        align(RIGHT)
        t = text(quip, x,y, width=95, height=65)
        rect(t.frame, dash=3, stroke=.7, fill=None)

    @reference('typography/fontsize.png')
    def test_fontsize(self):
        # ref/Typography/compat/fontsize()
        size(125, 125)
        fill(0.2)
        font("Helvetica")
        fontsize(35)
        text("hello", 10, 50)

    @reference('typography/lineheight.png')
    def test_lineheight(self):
        # ref/Typography/compat/lineheight()
        size(125, 125)
        fill(0.2)
        fontsize(16)
        lineheight(0.4)
        quip = "If it ain't fun make it fun"
        text(quip, 10, 55, width=80)

    @reference('typography/font-metrics.png')
    def test_font_metrics(self):
        # ref/Typography/types/Font
        size(270, 170)
        f = font('Palatino',110)
        pt = Point(10,120)
        with pen(2):
            line(pt-(0, f.ascender), stroke='steelblue', dx=250)
            line(pt-(0, f.capheight), stroke='orange', dx=250)
            line(pt-(0, f.xheight), stroke='red', dx=250)
            line(pt, dash=3, stroke='grey', dx=250)
            line(pt-(0, f.descender), stroke='green', dx=250)
        text(pt, str="Tulip")

    @reference('typography/line-fragment.png')
    def test_line_fragment(self):
        # ref/Typography/types/TextFragment
        size(270, 150)
        font('avenir', 32)
        layout(leading=1.6)
        t = text(20,60, 230, str='Blixa Bargeld, poet laureate')
        
        nofill()
        for slug in t.lines:
            rect(slug.frame, stroke=.9)  # faint
            rect(slug.bounds, stroke=.6) # dark
            arc(slug.baseline, 4, fill='red')


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TypographyTests))
  return suite
