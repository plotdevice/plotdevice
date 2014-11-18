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

        // shift the glyph's location by the line- and frame-offsets
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
        [path appendBezierPathWithGlyph:glyph inFont:font];
        [path closePath];
    }

    return path;
}

+ (NSArray *)lineFragmentsInRange:(NSRange)rng withLayout:(NSLayoutManager *)layout{
    NSRange full_range = [layout glyphRangeForCharacterRange:rng actualCharacterRange:NULL];
    NSArray *frames = [layout textContainers];
    NSString *text = [[layout textStorage] string];
    NSMutableArray *fragments = [NSMutableArray array];

    NSUInteger cursor = full_range.location;
    while(cursor<NSMaxRange(full_range)){
        // bail out if we've reached text that overflows the available containers
        NSTextContainer *frame_ref = [layout textContainerForGlyphAtIndex:cursor effectiveRange:NULL];
        if (!frame_ref) break;

        // measure the line fragment's bounds
        NSRange line_range;
        NSRect line_rect = [layout lineFragmentRectForGlyphAtIndex:cursor effectiveRange:&line_range];

        // update the ranges based on what's actually displayed in the bounds
        NSRange glyph_range = NSIntersectionRange(line_range, full_range);
        NSRange char_range = [layout characterRangeForGlyphRange:glyph_range actualGlyphRange:NULL];

        // measure the portion of the line that's included in the glyph range (clipped against the
        // line fragment's `used` rect to prevent \n from gobbling the entire column width)
        NSRect bounds_rect = [layout boundingRectForGlyphRange:glyph_range inTextContainer:frame_ref];
        NSRect used_rect = [layout lineFragmentUsedRectForGlyphAtIndex:cursor effectiveRange:NULL];
        NSRect glyph_rect = NSIntersectionRect(bounds_rect, used_rect);

        // calculate the baseline origin for the first glyph in the line
        NSPoint glyph_pt = [layout locationForGlyphAtIndex:cursor];
        NSPoint baseline = NSOffsetRect(line_rect, glyph_pt.x, glyph_pt.y).origin;

        // package the measurements
        [fragments addObject:@{
            @"slug": [NSValue valueWithRect:line_rect],
            @"bounds": [NSValue valueWithRect:glyph_rect],
            @"text": [text substringWithRange:char_range],
            @"range": [NSValue valueWithRange:char_range],
            @"frame": [NSNumber numberWithUnsignedLong:[frames indexOfObject:frame_ref]],
            @"baseline": [NSValue valueWithPoint:baseline]
        }];

        cursor = NSMaxRange(line_range);
    }
    return fragments;
}

+ (NSArray *)textContainersInRange:(NSRange)rng withLayout:(NSLayoutManager *)layout{
  NSRange full_range = [layout glyphRangeForCharacterRange:rng actualCharacterRange:NULL];
  NSMutableArray *frame_idxs = [NSMutableArray array];

  NSArray *containers = [layout textContainers];
  for (NSTextContainer *container in containers){
    NSRange frame_range = [layout glyphRangeForTextContainer:container];
    if (NSIntersectionRange(frame_range, full_range).length>0){
      [frame_idxs addObject:@([containers indexOfObject:container])];
    }
  }
  return frame_idxs;
}
@end