//
//  Vandercook.m
//  PlotDevice
//
//  Created by Christian Swinehart on 11/08/14.
//
//

#import "Vandercook.h"
#import <CoreText/SFNTLayoutTypes.h>

static NSDictionary *AAT;

@implementation Vandercook

+ (void)initialize{
  AAT = @{
      // lig
      @"Ligatures":@(kLigaturesType),
      @"CommonOn":@(kCommonLigaturesOnSelector),
      @"CommonOff":@(kCommonLigaturesOffSelector),
      @"ContextualOn":@(kContextualLigaturesOnSelector),
      @"ContextualOff":@(kContextualLigaturesOffSelector),
      @"RareOn":@(kRareLigaturesOnSelector),
      @"RareOff":@(kRareLigaturesOffSelector),
      @"HistoricalOn":@(kHistoricalLigaturesOnSelector),
      @"HistoricalOff":@(kHistoricalLigaturesOffSelector),

      // sc (both cases share the same selector values)
      @"LowerCase":@(kLowerCaseType), @"UpperCase":@(kUpperCaseType),
      @"DefaultCase":@(kDefaultLowerCaseSelector),
      @"SmallCaps":@(kLowerCaseSmallCapsSelector),

      // osf
      @"NumberCase":@(kNumberCaseType),
      @"LowerCaseNumbers":@(kLowerCaseNumbersSelector),
      @"UpperCaseNumbers":@(kUpperCaseNumbersSelector),

      // tab
      @"NumberSpacing":@(kNumberSpacingType),
      @"Monospaced":@(kMonospacedNumbersSelector),
      @"Proportional":@(kProportionalNumbersSelector),

      // frac
      @"Fractions":@(kFractionsType),
      @"NoFractions":@(kNoFractionsSelector),
      @"Diagonal":@(kDiagonalFractionsSelector),

      // vpos
      @"VerticalPosition":@(kVerticalPositionType),
      @"NormalPosition":@(kNormalPositionSelector),
      @"Superiors":@(kSuperiorsSelector),
      @"Inferiors":@(kInferiorsSelector),
      @"Ordinals":@(kOrdinalsSelector),

      // ss
      @"Alternates":@(kStylisticAlternativesType),
  };
  [AAT retain];
}

+ (NSDictionary *)aatAttributes:(NSDictionary *)options{
  NSMutableArray *settings = [NSMutableArray array];
  for (NSArray *pair in options){
    NSNumber *type = AAT[pair[0]];
    NSNumber *sel = nil;

    if ([pair[0] isEqualToString:@"Alternates"]){
      sel = @([pair[1] intValue] * 2);
    }else{
      sel = AAT[pair[1]];
    }
    [settings addObject:@{NSFontFeatureTypeIdentifierKey:type, NSFontFeatureSelectorIdentifierKey:sel}];
  }

  return @{NSFontFeatureSettingsAttribute:settings};
}


+ (NSBezierPath *)traceGlyphs:(NSRange)rng atOffset:(NSPoint)offset withLayout:(NSLayoutManager *)layout{
    NSRange glyph_range = [layout glyphRangeForCharacterRange:rng actualCharacterRange:NULL];

    NSBezierPath *path = [NSBezierPath bezierPath];
    NSTextStorage *store = layout.textStorage;
    NSUInteger start = glyph_range.location;
    NSUInteger end = NSMaxRange(glyph_range);

    for (NSUInteger glyph_idx=start; glyph_idx<end; glyph_idx++){
        // don't draw tabs, newlines, etc.
        if([layout notShownAttributeForGlyphAtIndex:glyph_idx]) continue;

        // shift the glyph's location by the line- and block-offsets
        NSRect line_rect = [layout lineFragmentRectForGlyphAtIndex:glyph_idx effectiveRange:nil];
        NSPoint glyph_pt = [layout locationForGlyphAtIndex:glyph_idx];
        glyph_pt.x += line_rect.origin.x + offset.x;
        glyph_pt.y += line_rect.origin.y + offset.y;
        glyph_pt.y *= -1;
        [path moveToPoint:glyph_pt];

        // add the glyph to the path
        NSUInteger txt_idx = [layout characterIndexForGlyphAtIndex:glyph_idx];
        NSFont *font = [store attribute:@"NSFont" atIndex:txt_idx effectiveRange:nil];
        NSGlyph glyph = [layout glyphAtIndex:glyph_idx];
        [path appendBezierPathWithCGGlyph:glyph inFont:font];
        [path closePath];
    }

    return path;
}

+ (NSArray *)lineFragmentsInRange:(NSRange)rng withLayout:(NSLayoutManager *)layout{
    NSRange full_range = [layout glyphRangeForCharacterRange:rng actualCharacterRange:NULL];
    NSArray *blocks = [layout textContainers];
    NSTextStorage *store = [layout textStorage];
    NSMutableArray *fragments = [NSMutableArray array];

    NSUInteger cursor = full_range.location;
    while(cursor<NSMaxRange(full_range)){
        // bail out if we've reached text that overflows the available containers
        NSTextContainer *block_ref = [layout textContainerForGlyphAtIndex:cursor effectiveRange:NULL];
        if (!block_ref) break;

        // measure the line fragment's bounds
        NSRange line_range;
        NSRect bounds_rect = [layout lineFragmentRectForGlyphAtIndex:cursor effectiveRange:&line_range];

        // update the ranges based on what's actually displayed in the bounds
        NSRange glyph_range = NSIntersectionRange(line_range, full_range);
        NSRange char_range = [layout characterRangeForGlyphRange:glyph_range actualGlyphRange:NULL];

        // measure the portion of the line that's `used' by glyphs, then adjust its left and right
        // edges if the glyph range under consideration is narrower than the full line
        NSRect used_rect = [layout lineFragmentUsedRectForGlyphAtIndex:cursor effectiveRange:NULL];
        if (NSLocationInRange(full_range.location, line_range)){
          NSPoint head = [layout locationForGlyphAtIndex:cursor];
          used_rect.size.width -= head.x - used_rect.origin.x;
          used_rect.origin.x = head.x;
        }
        if (NSLocationInRange(NSMaxRange(full_range), line_range)){
          NSPoint tail = [layout locationForGlyphAtIndex:NSMaxRange(full_range)];
          used_rect.size.width = tail.x - used_rect.origin.x;
        }

        // grab the baseline origin for the first glyph *before* shifting the bounds rects
        NSPoint baseline = NSMakePoint(used_rect.origin.x, bounds_rect.origin.y);

        // adjust the rects to reflect the baseline offset; note that since this relies on the font's
        // metrics rather than optical glyph bounds it could be way off if the designer was sloppy...
        NSFont *glyph_font = [store attribute:@"NSFont" atIndex:char_range.location effectiveRange:nil];
        bounds_rect.origin.y -= [glyph_font ascender];
        used_rect.origin.y -= [glyph_font ascender];

        // have the glyph-bounds rect exclude any extra lead
        used_rect.size.height = [glyph_font ascender] - [glyph_font descender];

        // package the measurements
        [fragments addObject:@{
            @"bounds": [NSValue valueWithRect:used_rect],
            @"frame": [NSValue valueWithRect:bounds_rect],
            @"range": [NSValue valueWithRange:char_range],
            @"block": [NSNumber numberWithUnsignedLong:[blocks indexOfObject:block_ref]],
            @"baseline": [NSValue valueWithPoint:baseline]
        }];

        cursor = NSMaxRange(line_range);
    }
    return fragments;
}

+ (NSArray *)textContainersInRange:(NSRange)rng withLayout:(NSLayoutManager *)layout{
  NSRange full_range = [layout glyphRangeForCharacterRange:rng actualCharacterRange:NULL];
  NSMutableArray *block_idxs = [NSMutableArray array];

  NSArray *containers = [layout textContainers];
  for (NSTextContainer *container in containers){
    NSRange block_range = [layout glyphRangeForTextContainer:container];
    if (NSIntersectionRange(block_range, full_range).length>0){
      [block_idxs addObject:@([containers indexOfObject:container])];
    }
  }
  return block_idxs;
}
@end